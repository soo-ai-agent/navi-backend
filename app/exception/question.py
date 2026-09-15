from __future__ import annotations


class SavingConditionsUnavailableError(Exception):
    """선택한 기간에 검증된 상품 조건이 없어 비교할 수 없다."""
