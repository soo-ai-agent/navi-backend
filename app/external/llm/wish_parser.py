from __future__ import annotations
import json
from typing import TYPE_CHECKING
from app.constants.question_text import GOAL_AMOUNT_KEY
from app.constants.wish_prompt import WISH_PROMPT
from app.enums.answer_kind import AnswerKind
from app.enums.judge_kind import JudgeKind
from app.external.llm import ChatMessage
from app.model.database.question import Question
from app.model.vo.wish_structure_vo import WishStructureVO

if TYPE_CHECKING:
    from typing import Sequence

    from app.external.llm import LlmClient

_PARSE_MAX_TOKENS = 16384
"""구조화 응답 토큰 한도. 추론 토큰이 4096 기본값을 다 쓰면 본문 없이 잘린다"""


def _goal_amount_question() -> Question:
    """goal_amount 는 DB question 이 아니라 응답에서 합성되는 키다 — 파서가 뽑을 수 있게 여기서만 알려준다.
    judge_kind 는 파서가 쓰지 않는다 (Entity 필수 컬럼이라 채울 뿐).
    모듈 적재 시점에 Entity 를 만들면 다른 모델이 import 되기 전에 매퍼 구성이 돌아 깨진다 — 호출 시점에 만든다."""
    return Question(
        code=GOAL_AMOUNT_KEY, title="만기까지 모으고 싶은 금액이 있나요? (원)",
        answer_kind=AnswerKind.NUMBER, judge_kind=JudgeKind.PRINCIPAL,
    )


class WishLlmParser:
    _llm_client: LlmClient

    def __init__(self, llm_client: LlmClient) -> None:
        self._llm_client = llm_client

    async def parse(self, message: str, questions: Sequence[Question]) -> WishStructureVO:
        asked: tuple[Question, ...] = tuple(questions) + (_goal_amount_question(),)
        schema: str = json.dumps(WishStructureVO.model_json_schema(), ensure_ascii=False)
        question_lines: str = "\n".join(
            f"- {question.code}: {question.title} ({question.answer_kind.value})" for question in asked
        )
        prompt: str = f"{WISH_PROMPT}\n질문 목록(code: 질문, 답 형식):\n{question_lines}\n{schema}"

        answer: str = await self._llm_client.ask_json((
            ChatMessage(role="system", content=prompt),
            ChatMessage(role="user", content=message),
        ), max_tokens=_PARSE_MAX_TOKENS, purpose="문장구조화")
        structured: WishStructureVO = WishStructureVO.model_validate_json(answer)

        codes: frozenset[str] = frozenset(question.code for question in asked)
        numeric_codes: frozenset[str] = frozenset(
            question.code for question in asked
            if question.answer_kind in (AnswerKind.NUMBER, AnswerKind.NUMBER_WITH_OPTIONS)
            or question.judge_kind is JudgeKind.SAVING_TERM
        )
        return structured.keep_known(codes).keep_numeric(numeric_codes)
