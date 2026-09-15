from __future__ import annotations

from pydantic import ConfigDict, RootModel, StrictStr

from app.model.vo.answer_vo import AnswerVO
from app.model.vo.answers_vo import AnswersVO


# 동적 질문 키를 가진 JSON 객체이므로 이 HTTP 경계에서만 dict를 사용한다.
class AnswerRequestDTO(RootModel[dict[str, StrictStr]]):
    model_config = ConfigDict(frozen=True)

    def to_answers(self) -> AnswersVO:
        return AnswersVO(tuple(
            AnswerVO(key, value) for key, value in self.root.items()
        ))
