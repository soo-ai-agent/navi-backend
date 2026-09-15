from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.dto.request.wish import WishRequestDTO
from app.dto.response.wish import WishResponseDTO
from app.service.wish.wish_structure import WishStructureService
from bootstrap.container.application import ApplicationConfig

router = APIRouter(prefix="/api/v1", tags=["wish"])


@router.post("/wishes")
@inject
async def create_wish(
    wish: WishRequestDTO,
    wish_structure_service: WishStructureService = Depends(Provide[ApplicationConfig.service.wish_structure_service])
) -> WishResponseDTO:
    """
    문장 대화의 한 턴. 새 문장이 있으면 구조화해 저장하고, 답이 쌓인 만큼 판정한다.

    질문이 남았으면 next.question 을 돌려주고, 다 채워졌을 때만 상황 순위(ranked)가 실린다.
    서버는 답을 저장하지 않으므로 매 요청에 답 전체가 실려 온다.
    """
    return await wish_structure_service.structure(wish.message, wish.to_answers(), wish.situation)
