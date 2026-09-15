from __future__ import annotations

from dataclasses import dataclass

from app.enums.saving_condition import ConditionStatus


@dataclass(frozen=True)
class ExcludedSavingVO:
    product_id: str
    stored_status: str
    status: ConditionStatus
    reason: str
