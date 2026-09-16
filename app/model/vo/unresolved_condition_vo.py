from __future__ import annotations
from pydantic import Field
from app.model.vo.condition_evidence_vo import ConditionEvidenceVO


class UnresolvedConditionVO(ConditionEvidenceVO):
    reason: str = Field(min_length=1, max_length=1000)
