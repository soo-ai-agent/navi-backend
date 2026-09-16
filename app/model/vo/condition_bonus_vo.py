from __future__ import annotations
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from app.model.vo.condition_group_vo import ConditionGroupVO


class ConditionBonusVO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(min_length=1, max_length=60)
    percentage_point: Decimal = Field(gt=0, le=10, allow_inf_nan=False)
    condition: ConditionGroupVO
