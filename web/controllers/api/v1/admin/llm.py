from __future__ import annotations
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from app.dto.request.admin_llm import (
    ConditionLlmTestRequestDTO, WishParseLlmTestRequestDTO, WishRankLlmTestRequestDTO, WishReplyLlmTestRequestDTO
)
from app.dto.response.admin_llm import LlmTestResponseDTO
from app.service.admin.llm_test import AdminLlmTestService
from bootstrap.container.application import ApplicationConfig

router = APIRouter(prefix="/api/v1/admin/llm", tags=["admin-llm"])


@router.post("/condition-parse")
@inject
async def test_condition_parse(
    body: ConditionLlmTestRequestDTO,
    admin_llm_test_service: AdminLlmTestService = Depends(Provide[ApplicationConfig.service.admin_llm_test_service])
) -> LlmTestResponseDTO:
    """공시 우대조건 구조화(ConditionLlmParser) 단건 시험. DB 의 공시 원문으로 실행하고 저장하지 않는다."""
    return await admin_llm_test_service.test_condition_parse(body.product_id)


@router.post("/wish-parse")
@inject
async def test_wish_parse(
    body: WishParseLlmTestRequestDTO,
    admin_llm_test_service: AdminLlmTestService = Depends(Provide[ApplicationConfig.service.admin_llm_test_service])
) -> LlmTestResponseDTO:
    """문장 답변 구조화(WishLlmParser) 단건 시험. 운영과 같은 질문 목록으로 실행하고 저장하지 않는다."""
    return await admin_llm_test_service.test_wish_parse(body.message)


@router.post("/wish-rank")
@inject
async def test_wish_rank(
    body: WishRankLlmTestRequestDTO,
    admin_llm_test_service: AdminLlmTestService = Depends(Provide[ApplicationConfig.service.admin_llm_test_service])
) -> LlmTestResponseDTO:
    """순위(WishLlmRanker) 단건 시험. /wishes 와 같은 재료로 후보를 모아 실행한다."""
    return await admin_llm_test_service.test_wish_rank(body.message, body.answers)


@router.post("/wish-reply")
@inject
async def test_wish_reply(
    body: WishReplyLlmTestRequestDTO,
    admin_llm_test_service: AdminLlmTestService = Depends(Provide[ApplicationConfig.service.admin_llm_test_service])
) -> LlmTestResponseDTO:
    """안내문(WishReplyWriter) 단건 시험. 답 상태로 다음 질문을 판정해 실행한다."""
    return await admin_llm_test_service.test_wish_reply(body.answers)
