from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO


class ManualConditionsVO(BaseModel):
    """직접 작성한 조건을 검토 당시 공시 원문에만 적용한다."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1, max_length=64)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    conditions: ExtractedConditionsVO

    def verify_source(self, source: SavingConditionSourceVO) -> None:
        if self.product_id != source.product_id or self.source_hash != source.source_hash():
            raise ValueError(f"검토 당시와 공시 원문이 다릅니다: {self.product_id}")
