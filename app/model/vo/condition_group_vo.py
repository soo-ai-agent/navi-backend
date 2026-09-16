from __future__ import annotations
from typing import assert_never
from pydantic import BaseModel, ConfigDict, Field
from app.constants.saving_condition import MAX_CONDITION_COUNT, MAX_CONDITION_DEPTH
from app.enums.saving_condition import ConditionMatch
from app.enums.saving import BonusResult
from app.exception.condition import ConditionVerificationError
from app.model.vo.answers_vo import AnswersVO
from app.model.vo.condition_answer_vo import ConditionAnswerVO
from app.model.vo.condition_context_vo import ConditionContextVO
from app.model.vo.condition_predicate_vo import ConditionPredicateVO


class ConditionGroupVO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    match: ConditionMatch
    conditions: tuple[ConditionPredicateVO | ConditionGroupVO, ...] = Field(max_length=30)

    def predicates(self, depth: int = 0) -> tuple[ConditionPredicateVO, ...]:
        if depth > MAX_CONDITION_DEPTH:
            raise ConditionVerificationError("조건 중첩이 너무 깊습니다")
        if not self.conditions and (depth > 0 or self.match is ConditionMatch.ANY):
            raise ConditionVerificationError("빈 복합조건은 허용하지 않습니다")
        predicates: list[ConditionPredicateVO] = []
        for condition in self.conditions:
            if isinstance(condition, ConditionGroupVO):
                predicates.extend(condition.predicates(depth + 1))
            else:
                predicates.append(condition)
        if len(predicates) > MAX_CONDITION_COUNT:
            raise ValueError("조건 수가 너무 많습니다")
        return tuple(predicates)

    def evaluate(self, answers: AnswersVO, context: ConditionContextVO) -> BonusResult:
        results: list[BonusResult] = []
        for condition in self.conditions:
            results.append(condition.evaluate(answers, context))

        match self.match:
            case ConditionMatch.ALL:
                return self._all_result(results)
            case ConditionMatch.ANY:
                return self._any_result(results)
            case _:
                assert_never(self.match)

    @staticmethod
    def _all_result(results: list[BonusResult]) -> BonusResult:
        if BonusResult.NOT_ELIGIBLE in results:
            return BonusResult.NOT_ELIGIBLE

        if BonusResult.UNKNOWN in results:
            return BonusResult.UNKNOWN

        return BonusResult.ELIGIBLE

    @staticmethod
    def _any_result(results: list[BonusResult]) -> BonusResult:
        if BonusResult.ELIGIBLE in results:
            return BonusResult.ELIGIBLE

        if BonusResult.UNKNOWN in results:
            return BonusResult.UNKNOWN

        return BonusResult.NOT_ELIGIBLE

    def unanswered(self, answers: AnswersVO, context: ConditionContextVO) -> tuple[ConditionAnswerVO, ...]:
        if self.evaluate(answers, context) is not BonusResult.UNKNOWN:
            return ()

        unanswered: list[ConditionAnswerVO] = []
        for condition in self.conditions:
            unanswered.extend(condition.unanswered(answers, context))
        return tuple(unanswered)
