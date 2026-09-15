from __future__ import annotations

from dataclasses import dataclass

from app.enums.saving import BonusResult
from app.model.vo.condition_answer_vo import ConditionAnswerVO
from app.model.vo.condition_bonus_vo import ConditionBonusVO


@dataclass(frozen=True)
class CheckedBonusVO:
    bonus: ConditionBonusVO
    result: BonusResult
    unanswered: tuple[ConditionAnswerVO, ...] = ()
