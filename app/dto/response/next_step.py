from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dto.response.question import QuestionResponseDTO
from app.dto.response.ranking import RankingResultResponseDTO
from app.enums.next_step import NextStepStatus


class NextStepResponseDTO(BaseModel):
    """
    턴 하나의 응답. status 로 갈라지는 두 형태다 (docs/server-client-flow.md).

    QUESTION 이면 question 이, DONE 이면 result 가 채워진다.
    """

    model_config = ConfigDict(frozen=True)

    status: NextStepStatus

    question: QuestionResponseDTO | None = None
    """DONE 일 때는 물을 것이 없으므로 null"""

    result: RankingResultResponseDTO | None = None
    """QUESTION 일 때는 순위가 아직 확정되지 않았으므로 null"""

    @classmethod
    def of_question(cls, question: QuestionResponseDTO) -> NextStepResponseDTO:
        return cls(status=NextStepStatus.QUESTION, question=question)

    @classmethod
    def of_result(cls, result: RankingResultResponseDTO) -> NextStepResponseDTO:
        return cls(status=NextStepStatus.DONE, result=result)
