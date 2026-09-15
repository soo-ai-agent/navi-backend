"""정책성 적금 언급 판정 — 공시 API 에 없는 정책 상품은 그 턴에 바로 안내한다."""

import logging
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.constants.policy_saving import POLICY_SAVING_NOTICE
from app.dto.response.next_step import NextStepResponseDTO
from app.dto.response.question import QuestionResponseDTO
from app.enums.answer_kind import AnswerKind
from app.external.llm.wish_parser import WishLlmParser
from app.external.llm.wish_reply_writer import WishReplyWriter
from app.model.vo.answers_vo import AnswersVO
from app.model.vo.questions_vo import QuestionsVO
from app.model.vo.wish_structure_vo import WishStructureVO
from app.service.question.question_flow import QuestionFlowService
from app.service.wish.wish import WishService
from app.service.wish.wish_ranking import WishRankingService
from app.service.wish.wish_structure import WishStructureService
from app.source.questions_source import QuestionsSource


def _question_step() -> NextStepResponseDTO:
    return NextStepResponseDTO.of_question(QuestionResponseDTO(
        key="months", title="몇 개월 저축하실 건가요?", answer_kind=AnswerKind.OPTIONS, options=(("12", "12개월"),),
    ))


def _service() -> WishStructureService:
    wish_service = AsyncMock(spec=WishService)
    wish_service.save.return_value = 1
    questions_source = AsyncMock(spec=QuestionsSource)
    questions_source.get.return_value = QuestionsVO(questions=())
    question_flow_service = AsyncMock(spec=QuestionFlowService)
    question_flow_service.next_step.return_value = _question_step()
    wish_ranking_service = AsyncMock(spec=WishRankingService)
    wish_parser = AsyncMock(spec=WishLlmParser)
    wish_parser.parse.return_value = WishStructureVO(answers=(), unmapped=())
    reply_writer = AsyncMock(spec=WishReplyWriter)
    reply_writer.write.return_value = "질문에 답해 주세요."
    return WishStructureService(
        wish_service, questions_source, question_flow_service, wish_ranking_service,
        wish_parser, reply_writer, logging.getLogger("test"),
    )


class PolicySavingNoticeTest(IsolatedAsyncioTestCase):

    async def test_군적금_언급_턴에는_안내가_reply_앞에_붙는다(self) -> None:
        service = _service()

        response = await service.structure("군적금 추천해줘", AnswersVO(), "")

        assert response.reply.startswith(POLICY_SAVING_NOTICE)
        # 기존 LLM 답변은 안내 뒤에 그대로 남는다
        assert "질문에 답해 주세요." in response.reply

    async def test_띄어쓰기가_섞여도_판정한다(self) -> None:
        service = _service()

        response = await service.structure("청년 도약 계좌 들고 싶어요", AnswersVO(), "")

        assert response.reply.startswith(POLICY_SAVING_NOTICE)

    async def test_일반_문장에는_안내가_없다(self) -> None:
        service = _service()

        response = await service.structure("12개월 적금 추천해줘", AnswersVO(), "")

        assert POLICY_SAVING_NOTICE not in response.reply
        assert response.reply == "질문에 답해 주세요."

    async def test_버튼_답_턴에는_재검사하지_않는다(self) -> None:
        service = _service()

        response = await service.structure(None, AnswersVO(), "군적금")

        assert POLICY_SAVING_NOTICE not in response.reply
        assert response.reply == ""
