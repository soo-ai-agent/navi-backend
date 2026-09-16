from __future__ import annotations
import hashlib
import json
from decimal import Decimal
from typing import assert_never
from pydantic import BaseModel, ConfigDict
from app.enums.saving_condition import ConditionSourceField
from app.enums.saving import JoinRestriction


class SavingConditionSourceVO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str
    name: str
    join_member: str
    join_restriction: JoinRestriction
    join_ways: str
    spcl_cnd: str
    etc_note: str
    monthly_limit: int | None  # 공시에서 한도 없음으로 제공한 경우
    saving_terms: tuple[int, ...]
    max_bonus_point: Decimal

    def source_hash(self) -> str:
        serialized: str = json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def text_of(self, field: ConditionSourceField) -> str:
        match field:
            case ConditionSourceField.JOIN_MEMBER:
                return self.join_member
            case ConditionSourceField.BONUS:
                return self.spcl_cnd
            case ConditionSourceField.NOTE:
                return self.etc_note
            case _:
                assert_never(field)

    @staticmethod
    def declares_no_bonus(text: str) -> bool:
        normalized: str = text.strip().replace(" ", "")
        return normalized in ("", "해당없음", "해당사항없음", "없음", "없습니다", "우대조건없음", "우대금리없음")
