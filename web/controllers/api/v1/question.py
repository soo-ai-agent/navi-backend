from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.dto.request.answer import AnswerRequestDTO
from app.dto.response.next_step import NextStepResponseDTO
from app.service.question.question_flow import QuestionFlowService
from bootstrap.container.application import ApplicationConfig

router = APIRouter(prefix="/api/v1", tags=["question"])


@router.post("/questions/next")
@inject
async def get_next_step(
    answers: AnswerRequestDTO,
    question_flow_service: QuestionFlowService = Depends(Provide[ApplicationConfig.service.question_flow_service])
) -> NextStepResponseDTO:
    """
    지금까지의 답을 받아 다음 질문 또는 확정 순위를 돌려준다.

    서버는 답을 저장하지 않으므로 매 요청에 답 전체가 실려 온다.
    """
    return await question_flow_service.next_step(answers.to_answers())
