from __future__ import annotations
from enum import Enum


class NextStepStatus(str, Enum):
    QUESTION = "question"
    DONE = "done"
