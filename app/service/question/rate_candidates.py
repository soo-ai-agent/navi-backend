from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.dto.response.question import QuestionResponseDTO
    from app.model.vo.excluded_saving_vo import ExcludedSavingVO
    from app.model.vo.saving_rate import SavingRate


@dataclass
class RateCandidates:
    rates: list[SavingRate] = field(default_factory=list)

    excluded: list[ExcludedSavingVO] = field(default_factory=list)

    checked_any_option: bool = False

    question: QuestionResponseDTO | None = None
