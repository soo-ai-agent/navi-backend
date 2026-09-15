from __future__ import annotations

from dataclasses import dataclass

from app.model.database.saving import Saving


@dataclass(frozen=True)
class SavingProductsVO:
    products: tuple[Saving, ...]

    def available_saving_terms(self) -> tuple[int, ...]:
        months: set[int] = set()
        for saving in self.products:
            for option in saving.rate_options:
                months.add(option.saving_term_months)
        return tuple(sorted(months))
