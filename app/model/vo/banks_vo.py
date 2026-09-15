from __future__ import annotations

from dataclasses import dataclass

from app.model.database.bank import Bank


@dataclass(frozen=True)
class BanksVO:
    banks: tuple[Bank, ...]

    def name(self, code: str) -> str:
        return self.of(code).display_name

    def of(self, code: str) -> Bank:
        for bank in self.banks:
            if bank.bank_code == code:
                return bank
        raise ValueError(f"상품의 은행을 찾을 수 없습니다: {code}")
