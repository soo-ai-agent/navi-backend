from __future__ import annotations
from logging import getLogger
from typing import TYPE_CHECKING
from pydantic import ValidationError
from infra.request_context import current_request_id
from app.dto.response.admin_llm import LlmTestResponseDTO
from app.exception.saving import SavingNotFoundError
from app.external.llm import LlmClient
from app.external.llm.condition_parser import ConditionLlmParser, ConditionParseResult
from app.external.llm.exception import ConditionLlmParseError
from app.external.llm.wish_parser import WishLlmParser
from app.external.llm.wish_ranker import WishLlmRanker
from app.external.llm.wish_reply_writer import WishReplyWriter
from app.model.vo.answer_vo import AnswerVO
from app.model.vo.answers_vo import AnswersVO
from app.model.vo.wish_structure_vo import WishStructureVO
from app.service.wish.wish_ranking import WishRanking, WishRankingService

if TYPE_CHECKING:
    from logging import Logger
    from typing import Sequence

    from app.dto.response.next_step import NextStepResponseDTO
    from app.external.llm import ChatMessage
    from app.model.database.saving import Saving
    from app.model.vo.questions_vo import QuestionsVO
    from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO
    from app.model.vo.saving_products_vo import SavingProductsVO
    from app.service.question.question_flow import QuestionFlowService
    from app.source.banks_source import BanksSource
    from app.source.questions_source import QuestionsSource
    from app.source.saving_products_source import SavingProductsSource

_NO_CANDIDATES = "후보 상품이 없어 LLM 을 호출하지 않았습니다."
_EMPTY_STRUCTURE = WishStructureVO(answers=(), unmapped=())
"""안내문 시험은 버튼 답 턴과 같은 재료다 — 구조화할 새 문장이 없다"""


class _RecordingLlmClient(LlmClient):
    """주입받은 클라이언트로 위임하면서 마지막 호출의 메시지와 원문 응답을 기록한다.

    운영 4종 클래스는 프롬프트·원시응답을 반환하지 않으므로, 운영 코드를 고치는 대신
    주입되는 클라이언트 자리에서 가로챈다 — 프롬프트 조립이 두 곳이 되지 않는다.
    LlmClient 상속은 운영 클래스들의 타입 계약을 맞추기 위해서고, 실제 호출은 origin 이 한다."""

    _origin: LlmClient
    messages: tuple[ChatMessage, ...]
    answer: str

    def __init__(self, origin: LlmClient) -> None:
        # 부모 설정은 쓰지 않는다 — 호출은 전부 origin 으로 위임한다. 로그도 origin 이 남긴다.
        super().__init__(base_url="", api_key="", model="", logger=getLogger(__name__))
        self._origin = origin
        self.messages = ()
        self.answer = ""

    # 기본값은 LlmClient.ask_json 과 같아야 한다 (재정의라 시그니처 호환이 필요하다).
    async def ask_json(
            self, messages: Sequence[ChatMessage], max_tokens: int = 4096,
            reasoning_effort: str = "medium", purpose: str = "일반",
    ) -> str:
        self.messages = tuple(messages)
        self.answer = await self._origin.ask_json(
            messages, max_tokens=max_tokens, reasoning_effort=reasoning_effort, purpose=purpose,
        )
        return self.answer

    def prompt(self) -> str:
        return self.messages[0].content if self.messages else ""

    def user_content(self) -> str:
        return self.messages[1].content if len(self.messages) > 1 else ""


class AdminLlmTestService:
    """관리자가 LLM 4종을 각각 한 번 실행해 프롬프트·원시응답·파싱 결과를 대조한다. DB 쓰기는 없다."""

    _llm_client: LlmClient
    _savings_source: SavingProductsSource
    _banks_source: BanksSource
    _questions_source: QuestionsSource
    _question_flow_service: QuestionFlowService
    _logger: Logger

    def __init__(
            self,
            llm_client: LlmClient,
            savings_source: SavingProductsSource,
            banks_source: BanksSource,
            questions_source: QuestionsSource,
            question_flow_service: QuestionFlowService,
            logger: Logger,
    ) -> None:
        self._llm_client = llm_client
        self._savings_source = savings_source
        self._banks_source = banks_source
        self._questions_source = questions_source
        self._question_flow_service = question_flow_service
        self._logger = logger

    async def test_condition_parse(self, product_id: str) -> LlmTestResponseDTO:
        """공시 우대조건 구조화(ConditionLlmParser)를 DB 의 공시 원문으로 한 번 실행한다."""
        products: SavingProductsVO = await self._savings_source.get(current_request_id())
        saving: Saving | None = next(
            (item for item in products.products if item.product_id == product_id), None,
        )
        if saving is None:
            raise SavingNotFoundError(f"상품을 찾을 수 없습니다: {product_id}")

        source: SavingConditionSourceVO = saving.condition_source()
        recorder: _RecordingLlmClient = _RecordingLlmClient(self._llm_client)
        try:
            result: ConditionParseResult = await ConditionLlmParser(recorder).parse(source)
        except ConditionLlmParseError as error:
            return self._to_response(recorder, parsed=None, parse_error=str(error.cause))
        return self._to_response(recorder, parsed=result.extracted, parse_error=None)

    async def test_wish_parse(self, message: str) -> LlmTestResponseDTO:
        """문장 답변 구조화(WishLlmParser)를 운영과 같은 질문 목록으로 한 번 실행한다."""
        questions: QuestionsVO = await self._questions_source.get(current_request_id())
        recorder: _RecordingLlmClient = _RecordingLlmClient(self._llm_client)
        try:
            structured: WishStructureVO = await WishLlmParser(recorder).parse(message, questions.questions)
        except (ValidationError, ValueError) as error:
            return self._to_response(recorder, parsed=None, parse_error=str(error))
        return self._to_response(recorder, parsed=structured, parse_error=None)

    async def test_wish_rank(self, message: str, answers: dict[str, str]) -> LlmTestResponseDTO:
        """순위(WishLlmRanker)를 /wishes 와 같은 재료(후보 수집·병합 포함)로 한 번 실행한다."""
        answers_vo: AnswersVO = _to_answers(answers)
        step: NextStepResponseDTO = await self._question_flow_service.next_step(answers_vo)

        recorder: _RecordingLlmClient = _RecordingLlmClient(self._llm_client)
        # 운영 클래스들은 클라이언트 말고는 상태가 없다. 기록용 클라이언트를 끼우려 호출마다 여기서 만든다.
        ranking_service: WishRankingService = WishRankingService(
            self._savings_source, self._banks_source, WishLlmRanker(recorder), self._logger,
        )
        try:
            ranking: WishRanking | None = await ranking_service.rank(
                current_request_id(), message, answers_vo, step, (),
            )
        except (ValidationError, ValueError) as error:
            return self._to_response(recorder, parsed=None, parse_error=str(error))

        if ranking is None:
            return self._to_response(recorder, parsed=None, parse_error=_NO_CANDIDATES)
        return self._to_response(recorder, parsed=ranking, parse_error=None)

    async def test_wish_reply(self, answers: dict[str, str]) -> LlmTestResponseDTO:
        """안내문(WishReplyWriter)을 질문 턴과 같은 재료(다음 질문 판정)로 한 번 실행한다."""
        answers_vo: AnswersVO = _to_answers(answers)
        step: NextStepResponseDTO = await self._question_flow_service.next_step(answers_vo)

        recorder: _RecordingLlmClient = _RecordingLlmClient(self._llm_client)
        try:
            reply: str = await WishReplyWriter(recorder).write(_EMPTY_STRUCTURE, step, ())
        except (ValidationError, ValueError) as error:
            return self._to_response(recorder, parsed=None, parse_error=str(error))
        return self._to_response(recorder, parsed=reply, parse_error=None)

    @staticmethod
    def _to_response(recorder: _RecordingLlmClient, parsed: object, parse_error: str | None) -> LlmTestResponseDTO:
        return LlmTestResponseDTO(
            prompt=recorder.prompt(), user_content=recorder.user_content(),
            raw_response=recorder.answer, parsed=parsed, parse_error=parse_error,
        )


def _to_answers(answers: dict[str, str]) -> AnswersVO:
    return AnswersVO(tuple(AnswerVO(key, value) for key, value in answers.items()))
