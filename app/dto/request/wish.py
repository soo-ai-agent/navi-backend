from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, StrictStr
from app.model.vo.answer_vo import AnswerVO
from app.model.vo.answers_vo import AnswersVO


class WishRequestDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    # 선택지 버튼으로만 답한 턴에는 구조화할 새 문장이 없다.
    message: StrictStr | None = Field(default=None, min_length=1, max_length=1000,
                                      description="이번 턴에 사용자가 새로 말한 문장")
    # 동적 질문 키를 가진 JSON 객체이므로 이 HTTP 경계에서만 dict를 사용한다.
    answers: dict[str, StrictStr] = Field(default_factory=dict, description="지금까지 쌓인 답 전체")
    situation: StrictStr = Field(default="", max_length=4000,
                                 description="사용자가 지금까지 말한 문장 전체. 최종 순위의 상황 근거로 쓴다")

    def to_answers(self) -> AnswersVO:
        return AnswersVO(tuple(
            AnswerVO(key, value) for key, value in self.answers.items()
        ))
