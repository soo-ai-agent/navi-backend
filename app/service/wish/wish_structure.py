from __future__ import annotations
from typing import TYPE_CHECKING
import httpx
from pydantic import ValidationError
from infra.request_context import current_request_id, short_request_id
from app.constants.policy_saving import POLICY_SAVING_KEYWORDS, POLICY_SAVING_NOTICE
from app.dto.response.wish import WishResponseDTO
from app.enums.next_step import NextStepStatus
from app.exception.wish import WishStructureError
from app.external.llm import LlmApiError
from app.model.database.user_wish import UserWish
from app.model.vo.answer_vo import AnswerVO
from app.model.vo.answers_vo import AnswersVO
from app.model.vo.wish_structure_vo import WishStructureVO

if TYPE_CHECKING:
    from logging import Logger

    from app.dto.response.next_step import NextStepResponseDTO
    from app.external.llm.wish_parser import WishLlmParser
    from app.external.llm.wish_reply_writer import WishReplyWriter
    from app.model.vo.questions_vo import QuestionsVO
    from app.service.question.question_flow import QuestionFlowService
    from app.service.wish.wish import WishService
    from app.service.wish.wish_ranking import WishRanking, WishRankingService
    from app.source.questions_source import QuestionsSource

_LLM_FAILURES = (LlmApiError, httpx.RequestError, httpx.TimeoutException, ValidationError, ValueError)
"""외부 AI 호출·응답 검증에서 나올 수 있는 실패. 도메인 오류로 번역해 사용자 안내로 바꾼다"""

_EMPTY_STRUCTURE = WishStructureVO(answers=(), unmapped=())
"""버튼으로만 답한 턴 — 구조화할 새 문장이 없다"""


class WishStructureService:
    """
    문장 대화의 한 턴을 처리한다.

    질문이 남았으면 질문을 돌려주고, 자격요건·우대사항이 다 채워졌을 때만
    LLM 상황 순위를 매긴다. 순위는 대화의 마지막에 한 번만 나온다.
    """

    _wish_service: WishService
    _questions_source: QuestionsSource
    _question_flow_service: QuestionFlowService
    _wish_ranking_service: WishRankingService
    _wish_parser: WishLlmParser
    _reply_writer: WishReplyWriter
    _logger: Logger

    def __init__(
            self,
            wish_service: WishService,
            questions_source: QuestionsSource,
            question_flow_service: QuestionFlowService,
            wish_ranking_service: WishRankingService,
            wish_parser: WishLlmParser,
            reply_writer: WishReplyWriter,
            logger: Logger,
    ) -> None:
        self._wish_service = wish_service
        self._questions_source = questions_source
        self._question_flow_service = question_flow_service
        self._wish_ranking_service = wish_ranking_service
        self._wish_parser = wish_parser
        self._reply_writer = reply_writer
        self._logger = logger

    async def structure(self, message: str | None, prior: AnswersVO, situation: str) -> WishResponseDTO:
        request_id: str = current_request_id()

        structured: WishStructureVO = _EMPTY_STRUCTURE
        wish_id: int | None = None
        if message is not None:
            structured, wish_id = await self._structure_message(request_id, message)

        answers: AnswersVO = self._merge(prior, structured)
        step: NextStepResponseDTO = await self._question_flow_service.next_step(answers)

        if step.status is NextStepStatus.QUESTION:
            response: WishResponseDTO = await self._question_turn(request_id, wish_id, structured, step, message)
        else:
            response = await self._ranking_turn(
                request_id, wish_id, structured, step, answers, situation or (message or ""),
            )

        # 정책성 적금(군적금·청년 정책 상품)은 공시 API 에 없어 추천 불가 — 새 문장이 있는 턴에만 판정한다.
        if message is not None and self._mentions_policy_saving(message):
            self._logger.info("정책 적금 안내 | req=%s | wish_id=%s", short_request_id(request_id), wish_id)
            joined_reply: str = f"{POLICY_SAVING_NOTICE}\n\n{response.reply}" if response.reply else POLICY_SAVING_NOTICE
            return response.model_copy(update={"reply": joined_reply})

        return response

    @staticmethod
    def _mentions_policy_saving(message: str) -> bool:
        compact: str = message.replace(" ", "")
        return any(keyword in compact for keyword in POLICY_SAVING_KEYWORDS)

    async def _structure_message(self, request_id: str, message: str) -> tuple[WishStructureVO, int]:
        questions: QuestionsVO = await self._questions_source.get(request_id)
        try:
            structured: WishStructureVO = await self._wish_parser.parse(message, questions.questions)
        except _LLM_FAILURES as error:
            raise self._structure_error(request_id, "요구 구조화", error)

        wish_id: int = await self._wish_service.save(UserWish.from_structured(message, structured))
        self._logger.info(
            "요구 구조화 저장 | req=%s | wish_id=%d | 매핑답변=%d | 보존항목=%d",
            short_request_id(request_id), wish_id, len(structured.answers), len(structured.unmapped),
        )
        return structured, wish_id

    @staticmethod
    def _merge(prior: AnswersVO, structured: WishStructureVO) -> AnswersVO:
        """이미 답한 값이 우선이다 — 문장 재해석이 버튼으로 확정한 답을 덮지 않는다."""
        merged: dict[str, str] = {answer.code: answer.value for answer in structured.answers}
        merged.update({entry.key: entry.value for entry in prior.entries})
        return AnswersVO(tuple(AnswerVO(key, value) for key, value in merged.items()))

    async def _question_turn(
            self, request_id: str, wish_id: int | None, structured: WishStructureVO,
            step: NextStepResponseDTO, message: str | None,
    ) -> WishResponseDTO:
        """질문이 남은 턴. 버튼 답 턴은 LLM 없이 즉시 돌려준다 — 프론트가 질문을 그린다."""
        reply: str = ""
        if message is not None:
            try:
                reply = await self._reply_writer.write(structured, step, (), message)
            except _LLM_FAILURES as error:
                raise self._structure_error(request_id, "답변 생성", error)

        return WishResponseDTO.from_structured(wish_id, structured, reply, step, ())

    async def _ranking_turn(
            self, request_id: str, wish_id: int | None, structured: WishStructureVO,
            step: NextStepResponseDTO, answers: AnswersVO, situation: str,
    ) -> WishResponseDTO:
        """모든 질문이 채워진 턴. 이때만 LLM 이 상황 순위와 마무리 문장을 만든다."""
        try:
            ranking: WishRanking | None = await self._wish_ranking_service.rank(
                request_id, situation, answers, step, structured.unmapped,
            )
        except _LLM_FAILURES as error:
            self._logger.error(
                "순위 판단 실패 | req=%s | 오류=%s | 사유=%s",
                short_request_id(request_id), type(error).__name__, _safe_reason(error),
            )
            ranking = None

        if ranking is None:
            # 상황 순위 없이도 규칙 엔진 순위(next.result)는 내려간다.
            return WishResponseDTO.from_structured(wish_id, structured, "", step, ())

        return WishResponseDTO.from_structured(wish_id, structured, ranking.reply, step, ranking.rows)

    def _structure_error(self, request_id: str, stage: str, error: Exception) -> WishStructureError:
        # 외부 AI 실패·응답 형식 오류를 도메인 오류로 번역한다. 응답 본문은 노출하지 않는다.
        self._logger.error(
            "%s 실패 | req=%s | 오류=%s | 사유=%s",
            stage, short_request_id(request_id), type(error).__name__, _safe_reason(error),
        )
        return WishStructureError(f"{stage}에 실패했습니다. 잠시 후 다시 시도해 주세요.")


def _safe_reason(error: Exception) -> str:
    """로그에 실어도 안전한 실패 원인. LLM·연결 오류만 문장을 싣는다 — 검증 오류의 str 은 응답 본문을 담을 수 있다."""
    if isinstance(error, (LlmApiError, httpx.RequestError, httpx.TimeoutException)):
        return str(error)
    return "응답 형식 오류"
