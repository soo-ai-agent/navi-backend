from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.enums.saving_condition import ConditionSourceField


class ConditionEvidenceVO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_field: ConditionSourceField
    source_text: str = Field(min_length=1, max_length=10000)
