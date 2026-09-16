from __future__ import annotations
import logging
import unicodedata

LOG_FORMAT = "%(levelname)-8s %(asctime)s %(message)s"
"""레벨명은 8자 고정 폭 — INFO·WARNING 길이 차이로 뒤 열이 밀리지 않게 한다."""

_ACTION_WIDTH = 28
"""행위명 열의 표시 폭. 가장 긴 행위명("직접 저장 전 DB 백업 완료" = 25칸)에 진행 접두 2칸을 더해도 남는다."""

_FIELD_SEPARATOR = " | "

_PROGRESS_PREFIX = "- "
"""요청 경계("요청 시작/종료/실패")가 아닌 처리 중간 진행 로그임을 나타내는 접두."""


class AlignedFormatter(logging.Formatter):
    """'행위 | key=value' 로그의 행위명을 고정 폭으로 채워 req 열부터 세로로 맞춘다."""

    def format(self, record: logging.LogRecord) -> str:
        message: str = record.getMessage()
        if _FIELD_SEPARATOR in message:
            action, rest = message.split(_FIELD_SEPARATOR, 1)
            if not action.startswith("요청"):
                action = _PROGRESS_PREFIX + action
            record.msg = _pad_display(action, _ACTION_WIDTH) + _FIELD_SEPARATOR + rest
            record.args = ()
        return super().format(record)


def _pad_display(text: str, width: int) -> str:
    """한글은 터미널에서 2칸을 차지하므로 글자 수가 아니라 표시 폭으로 채운다."""
    display_width: int = sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)
    return text + " " * max(width - display_width, 0)
