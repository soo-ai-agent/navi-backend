from __future__ import annotations
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from app.dto.response.raw_savings import RawSavingsResponseDTO
from app.dto.response.saving_refresh import SavingRefreshResponseDTO
from app.service.saving.raw_saving import RawSavingService
from app.service.saving.saving_refresh import SavingRefreshService
from bootstrap.container.application import ApplicationConfig

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/products/raw")
@inject
async def get_raw_savings(
    raw_saving_service: RawSavingService = Depends(Provide[ApplicationConfig.service.raw_saving_service])
) -> RawSavingsResponseDTO:
    """금감원 적금 공시 수신 결과. 수집이 정상인지 눈으로 확인한다."""
    return await raw_saving_service.get_savings()


@router.post("/products/refresh")
@inject
async def refresh_savings(
    saving_refresh_service: SavingRefreshService = Depends(Provide[ApplicationConfig.service.saving_refresh_service])
) -> SavingRefreshResponseDTO:
    """
    공시를 받아 상품을 갱신한다. 금감원 조회 → 저장 → 우대조건 구조화까지 한 번에 돈다.

    LLM 호출이 상품 수만큼 나가 수 분이 걸린다.
    """
    return await saving_refresh_service.refresh()
