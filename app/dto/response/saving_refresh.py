from __future__ import annotations
from pydantic import BaseModel, ConfigDict


class DisclosureSyncResponseDTO(BaseModel):
    """공시 적재 결과. 금감원에서 받아 DB 에 넣은 건수다."""

    model_config = ConfigDict(frozen=True)

    banks: int
    products: int
    rate_options: int
    bonus_reset_savings: int
    """우대조건 원문이 바뀌어 재번역이 필요해진 상품 수"""


class BonusStructureResponseDTO(BaseModel):
    """필수·우대조건 구조화 결과. 기존 갱신 응답의 bonus 키를 유지한다."""

    model_config = ConfigDict(frozen=True)

    scanned_savings: int

    structured_savings: int
    created_bonuses: int
    """기존 금리 판정기와 호환되는 ProductBonus 저장 건수"""

    not_structurable_savings: int
    """확인 필요·추출 실패·추출 중 원문 변경으로 저장하지 못한 상품 수"""

    skipped_savings: int
    """원문이 그대로라 다시 부르지 않은 상품"""


class SavingRefreshResponseDTO(BaseModel):
    """
    적금 상품 갱신 한 번의 결과.

    공시를 받아 저장하고, 바뀐 상품의 우대조건을 다시 구조화한 결과를 함께 돌려준다.
    """

    model_config = ConfigDict(frozen=True)

    disclosure: DisclosureSyncResponseDTO
    bonus: BonusStructureResponseDTO
