from __future__ import annotations

from enum import Enum


class AnswerKind(str, Enum):
    OPTIONS = "OPTIONS"

    NUMBER = "NUMBER"

    NUMBER_WITH_OPTIONS = "NUMBER_WITH_OPTIONS"

    BOOLEAN = "BOOLEAN"

    MULTI_OPTIONS = "MULTI_OPTIONS"
    """선택지에서 여러 개를 고른다. 답은 고른 값을 쉼표로 이은 문자열이다"""
