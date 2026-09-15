from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.dto.request.answer import AnswerRequestDTO
from app.dto.response.saving_catalog import CatalogSavingResponseDTO, SavingCatalogResponseDTO
from app.dto.response.saving_comparison import SavingComparisonsResponseDTO
from app.service.saving.saving_catalog import SavingCatalogService
from bootstrap.container.application import ApplicationConfig

router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.get("")
@inject
async def get_savings(
    saving_catalog_service: SavingCatalogService = Depends(Provide[ApplicationConfig.service.saving_catalog_service]),
) -> SavingCatalogResponseDTO:
    """저장된 모든 적금을 공시 금리와 함께 조회한다. 사용자 조건으로 필터링하지 않는다."""
    return await saving_catalog_service.catalog()


@router.post("/compare")
@inject
async def compare_savings(
    body: AnswerRequestDTO,
    saving_catalog_service: SavingCatalogService = Depends(Provide[ApplicationConfig.service.saving_catalog_service]),
) -> SavingComparisonsResponseDTO:
    """누적 답변으로 모든 상품의 금리·가입 가능 여부를 계산한다."""
    return await saving_catalog_service.compare(body.to_answers())


@router.get("/{product_id}")
@inject
async def get_saving(
    product_id: str,
    saving_catalog_service: SavingCatalogService = Depends(Provide[ApplicationConfig.service.saving_catalog_service]),
) -> CatalogSavingResponseDTO:
    """저장된 적금 한 건의 공시 상세를 조회한다."""
    return await saving_catalog_service.detail(product_id)
