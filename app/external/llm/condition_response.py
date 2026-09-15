from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import cast

from app.enums.saving_condition import ConditionField


# 외부 AI JSON 은 정의되지 않은 키·타입을 포함하므로 이 수신 경계에서만 dict 로 검사한다.
JsonObject = dict[str, object]

_INTEGER = re.compile(r"^[+-]?\d+$")
_TOP_LEVEL_FIELDS = {
    "eligibility", "bonuses", "unresolved", "bonus_status", "other_conditions",
    "other_eligibility_conditions", "other_bonus_conditions",
}
_GROUP_FIELDS = {"match", "conditions"}
_PREDICATE_FIELDS = {
    "source_field", "source_text", "field", "operator", "values", "question_key", "question_text"
}
_BONUS_FIELDS = {"label", "percentage_point", "condition"}
_UNRESOLVED_FIELDS = {"source_field", "source_text", "reason"}
_OTHER_FIELDS = {"name", "value", "reason"}

_CATEGORY_FIELDS = ("other_eligibility_conditions", "other_bonus_conditions")
"""자격·우대로 나눠 담는 체크리스트 항목들"""

_UNKNOWN_FIELD_REASON = "AI 응답의 정의되지 않은 필드. 사용자 체크리스트 표시 전용"


@dataclass
class _OtherConditionCollector:
    generic: list[JsonObject] = field(default_factory=list)
    eligibility: list[JsonObject] = field(default_factory=list)
    bonus: list[JsonObject] = field(default_factory=list)

    def add(self, path: str, value: object, reason: str) -> None:
        item: JsonObject = {"name": path, "value": _as_display_text(value), "reason": reason}
        self._bucket_for(path).append(item)

    def _bucket_for(self, path: str) -> list[JsonObject]:
        if path.startswith("eligibility") or path.startswith("other_eligibility_conditions"):
            return self.eligibility

        if path.startswith("bonuses") or path.startswith("other_bonus_conditions"):
            return self.bonus

        return self.generic


def normalize_condition_response(answer: str) -> str:
    """
    LLM 경계에서 타입 표기와 정의되지 않은 필드를 정리한다.

    json.loads 와 dict 는 외부 JSON 의 모양을 확인하는 경계에서만 사용한다.
    내부에는 이 함수가 만든 JSON 을 검증한 VO 만 전달한다.
    """
    parsed: object = json.loads(answer)
    if not isinstance(parsed, dict):
        raise ValueError("LLM 응답은 JSON 객체여야 합니다")

    payload: JsonObject = cast(JsonObject, parsed)
    collector = _OtherConditionCollector()
    _move_unknown_fields(payload, _TOP_LEVEL_FIELDS, "response", collector)

    # 가입조건은 없어도 된다 — 누구나 가입할 수 있는 상품이 있다.
    eligibility: object = payload.get("eligibility")
    if eligibility is not None:
        payload["eligibility"] = _normalize_group(eligibility, "eligibility", collector)

    bonuses: object = payload.get("bonuses")
    if isinstance(bonuses, list):
        payload["bonuses"] = _normalize_bonuses(bonuses, collector)

    unresolved: object = payload.get("unresolved")
    if isinstance(unresolved, list):
        payload["unresolved"] = _normalize_items(unresolved, "unresolved", _UNRESOLVED_FIELDS, collector)

    _normalize_checklist_fields(payload, collector)

    _append_collected(payload, "other_conditions", collector.generic)
    _append_collected(payload, "other_eligibility_conditions", collector.eligibility)
    _append_collected(payload, "other_bonus_conditions", collector.bonus)
    return json.dumps(payload, ensure_ascii=False)


def _normalize_checklist_fields(payload: JsonObject, collector: _OtherConditionCollector) -> None:
    for field_name in ("other_conditions",) + _CATEGORY_FIELDS:
        existing: object = payload.get(field_name, [])

        if not isinstance(existing, list):
            # 목록이 아닌 기타 조건은 모델 검증 오류로 남겨 입력 손상을 숨기지 않는다.
            payload[field_name] = existing
            continue

        payload[field_name] = _normalize_items(existing, field_name, _OTHER_FIELDS, collector)


def _normalize_bonuses(items: list[object], collector: _OtherConditionCollector) -> list[object]:
    normalized: list[object] = []

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            normalized.append(item)
            continue

        bonus: JsonObject = cast(JsonObject, item)
        _move_unknown_fields(bonus, _BONUS_FIELDS, f"bonuses[{index}]", collector)

        condition: object = bonus.get("condition")
        if isinstance(condition, dict):
            bonus["condition"] = _normalize_bonus_condition(condition, f"bonuses[{index}].condition", collector)

        normalized.append(bonus)

    return normalized


def _normalize_bonus_condition(condition: object, path: str, collector: _OtherConditionCollector) -> object:
    """우대조건은 판정할 조건이 반드시 있어야 한다 — 비면 공시 원문을 사람이 확인해야 한다."""
    normalized: object = _normalize_group(condition, path, collector)

    if not isinstance(normalized, dict) or not normalized.get("conditions"):
        raise ValueError("빈 우대조건은 자동 판정할 수 없어 공시 원문 확인이 필요합니다")

    return normalized


def _normalize_group(value: object, path: str, collector: _OtherConditionCollector) -> object:
    if not isinstance(value, dict):
        return value

    group: JsonObject = cast(JsonObject, value)
    _move_unknown_fields(group, _GROUP_FIELDS, path, collector)

    conditions: object = group.get("conditions")
    if not isinstance(conditions, list):
        return group

    normalized: list[object] = []
    for index, condition in enumerate(conditions):
        condition_path: str = f"{path}.conditions[{index}]"
        normalized.append(_normalize_condition(condition, condition_path, collector))

    group["conditions"] = normalized
    return group


def _normalize_condition(condition: object, path: str, collector: _OtherConditionCollector) -> object:
    if not isinstance(condition, dict):
        return condition

    item: JsonObject = cast(JsonObject, condition)

    if "field" in item:
        return _normalize_predicate(item, path, collector)

    if "match" in item:
        nested: object = _normalize_group(item, path, collector)
        if not isinstance(nested, dict) or not nested.get("conditions"):
            raise ValueError("빈 복합조건은 자동 판정할 수 없어 공시 원문 확인이 필요합니다")
        return nested

    return item


def _normalize_predicate(item: JsonObject, path: str, collector: _OtherConditionCollector) -> JsonObject:
    field_value: object = item.get("field")
    try:
        condition_field = ConditionField(cast(str, field_value))
    except (TypeError, ValueError) as error:
        # AND/OR 의 일부를 지우면 가입 자격·금리가 달라져 전체를 원문 체크리스트로 처리한다.
        raise ValueError("정의되지 않은 조건 필드가 있어 공시 원문 확인이 필요합니다") from error

    _move_unknown_fields(item, _PREDICATE_FIELDS, path, collector)

    values: object = item.get("values")
    if isinstance(values, list):
        item["values"] = [_normalize_value(condition_field, current) for current in values]

    return item


def _normalize_value(condition_field: ConditionField, value: object) -> object:
    expected = condition_field.value_type()

    if expected is int:
        return _as_int(value)

    if expected is bool:
        return _as_bool(value)

    return value


def _as_int(value: object) -> object:
    if type(value) is int:
        return value

    if isinstance(value, str) and _INTEGER.fullmatch(value.strip()):
        # AI 가 숫자를 문자열로 직렬화한 경우에만 모호하지 않게 복원한다.
        return int(value)

    return value


def _as_bool(value: object) -> object:
    if type(value) is bool:
        return value

    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        # true/false 외 문자열은 의미를 추정하지 않고 모델 검증에 맡긴다.
        return value.strip().lower() == "true"

    return value


def _normalize_items(
    items: list[object], path: str, allowed: set[str], collector: _OtherConditionCollector
) -> list[object]:
    normalized: list[object] = []

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            normalized.append(item)
            continue

        value: JsonObject = cast(JsonObject, item)
        _move_unknown_fields(value, allowed, f"{path}[{index}]", collector)
        normalized.append(value)

    return normalized


def _move_unknown_fields(value: JsonObject, allowed: set[str], path: str, collector: _OtherConditionCollector) -> None:
    for key in tuple(value):
        if key in allowed:
            continue

        unknown: object = value.pop(key)
        collector.add(f"{path}.{key}", unknown, _UNKNOWN_FIELD_REASON)


def _append_collected(payload: JsonObject, field_name: str, values: list[JsonObject]) -> None:
    current: object = payload.get(field_name, [])

    # 목록이 아닌 기타 조건은 모델 검증 오류로 남겨 입력 손상을 숨기지 않는다.
    if not isinstance(current, list):
        return

    current.extend(values)
    payload[field_name] = current


def _as_display_text(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
