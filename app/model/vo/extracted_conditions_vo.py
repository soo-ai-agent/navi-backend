from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.enums.saving_condition import BonusConditionStatus, ConditionMatch
from app.enums.saving import JoinRestriction
from app.exception.condition import ConditionVerificationError
from app.model.vo.condition_bonus_vo import ConditionBonusVO
from app.model.vo.condition_evidence_vo import ConditionEvidenceVO
from app.model.vo.condition_group_vo import ConditionGroupVO
from app.model.vo.condition_predicate_vo import ConditionPredicateVO
from app.model.vo.other_condition_vo import OtherConditionVO
from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO
from app.model.vo.unresolved_condition_vo import UnresolvedConditionVO


class ExtractedConditionsVO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    eligibility: ConditionGroupVO
    bonuses: tuple[ConditionBonusVO, ...] = Field(max_length=20)
    unresolved: tuple[UnresolvedConditionVO, ...] = Field(max_length=30)
    # 판정에 사용하지 않고 결과 화면의 체크리스트로만 보여주는 조건이다.
    other_conditions: tuple[OtherConditionVO, ...] = Field(default=(), max_length=30)
    other_eligibility_conditions: tuple[OtherConditionVO, ...] = Field(default=(), max_length=30)
    other_bonus_conditions: tuple[OtherConditionVO, ...] = Field(default=(), max_length=30)
    bonus_status: BonusConditionStatus = BonusConditionStatus.UNKNOWN

    @classmethod
    def from_source_checklist(cls, source: SavingConditionSourceVO) -> ExtractedConditionsVO:
        eligibility: list[OtherConditionVO] = []
        if source.join_member.strip():
            eligibility.append(OtherConditionVO(
                name="가입 대상", value=source.join_member,
                reason="가입 자격을 자동 판정하지 않았습니다. 원문에 해당하는지 확인해야 합니다.",
            ))
        if source.etc_note.strip():
            eligibility.append(OtherConditionVO(
                name="가입·납입 및 유의사항", value=source.etc_note,
                reason="납입 단위·계좌 제한 등 유의사항을 확인해야 합니다.",
            ))
        bonuses: tuple[OtherConditionVO, ...] = ()
        status: BonusConditionStatus = BonusConditionStatus.UNKNOWN
        if source.declares_no_bonus(source.spcl_cnd) and source.max_bonus_point == 0:
            status = BonusConditionStatus.NO_BONUS
        elif not source.declares_no_bonus(source.spcl_cnd):
            status = BonusConditionStatus.CHECKLIST
            bonuses = (OtherConditionVO(
                name="우대금리 적용 조건", value=source.spcl_cnd,
                reason="세부 조건과 적용 금리를 확인해야 합니다. 확인 전에는 표시 금리에 더하지 않습니다.",
            ),)
        return cls(
            eligibility=ConditionGroupVO(match=ConditionMatch.ALL, conditions=()),
            bonuses=(), unresolved=(), bonus_status=status,
            other_eligibility_conditions=tuple(eligibility), other_bonus_conditions=bonuses,
        )

    def with_source_status(self, source: SavingConditionSourceVO) -> ExtractedConditionsVO:
        return ExtractedConditionsVO(
            eligibility=self.eligibility, bonuses=self.bonuses, unresolved=self.unresolved,
            other_conditions=self.other_conditions,
            other_eligibility_conditions=self.other_eligibility_conditions,
            other_bonus_conditions=self.other_bonus_conditions,
            bonus_status=self._bonus_status_from_source(source),
        )

    def _bonus_status_from_source(self, source: SavingConditionSourceVO) -> BonusConditionStatus:
        """
        AI 가 말한 상태를 공시 원문으로 검산한다.

        원문에 우대가 없다고 적혀 있고 금리 차이도 없으면, AI 가 무어라 했든 우대금리 없음이다.
        """
        if self._has_no_bonus(source):
            return BonusConditionStatus.NO_BONUS

        if self.other_bonus_conditions and not self.unresolved:
            return BonusConditionStatus.CHECKLIST

        if self.bonus_status is BonusConditionStatus.AVAILABLE and self.unresolved:
            return BonusConditionStatus.UNKNOWN

        return self.bonus_status

    def _has_no_bonus(self, source: SavingConditionSourceVO) -> bool:
        """이 상품에 우대금리가 아예 없는가 — 추출 결과와 공시가 모두 없다고 말해야 한다."""
        nothing_extracted: bool = (
            not self.bonuses and not self.unresolved and not self.other_bonus_conditions
        )
        no_rate_gap: bool = source.max_bonus_point == 0
        declared_none: bool = source.declares_no_bonus(source.spcl_cnd)
        return nothing_extracted and no_rate_gap and declared_none

    def verify(self, source: SavingConditionSourceVO) -> None:
        self._verify_bonus_status(source)

        if self.bonus_status is BonusConditionStatus.CHECKLIST:
            self._verify_checklists(source)

        self._verify_evidence(source)
        self._verify_bonus_total(source)

    def _verify_evidence(self, source: SavingConditionSourceVO) -> None:
        """판정에 쓰는 모든 조건의 근거 문장이 공시 원문 안에 있어야 한다."""
        evidence: list[ConditionEvidenceVO] = list(self.eligibility.predicates())
        for bonus in self.bonuses:
            predicates: tuple[ConditionPredicateVO, ...] = bonus.condition.predicates()
            if not predicates:
                raise ConditionVerificationError("우대금리의 조건이 비어 있습니다")
            evidence.extend(predicates)
        evidence.extend(self.unresolved)

        for item in evidence:
            original: str = source.text_of(item.source_field)
            if not self._quoted_from(item.source_text, original):
                raise ConditionVerificationError("조건의 근거가 공시 원문에 없습니다")

    @staticmethod
    def _quoted_from(source_text: str, original: str) -> bool:
        """
        인용문의 모든 줄이 원문에 그대로 있는가.

        AI 가 "1.공통 조건 … 가.항목" 처럼 떨어진 줄을 이어 인용하는 일이 잦아
        줄 단위로 확인한다. 줄 하나라도 원문에 없으면 지어낸 근거다.
        """
        if not source_text.strip():
            return False
        lines: list[str] = [line.strip() for line in source_text.splitlines() if line.strip()]
        return all(line in original for line in lines)

    def _verify_bonus_total(self, source: SavingConditionSourceVO) -> None:
        """우대를 다 더해도 공시가 밝힌 최고 금리 폭을 넘을 수 없다."""
        total: Decimal = sum((bonus.percentage_point for bonus in self.bonuses), Decimal(0))
        if total > source.max_bonus_point:
            raise ConditionVerificationError("우대금리 합이 공시 상한을 넘습니다. 중복·차등 우대를 확인해야 합니다")

    def needs_review(self, source: SavingConditionSourceVO) -> bool:
        has_unresolved: bool = bool(self.unresolved)
        misses_join_condition: bool = self._misses_join_condition(source)
        misses_bonus_condition: bool = self._misses_bonus_condition(source)
        has_no_join_member: bool = not source.join_member.strip()

        return has_unresolved or misses_join_condition or misses_bonus_condition or has_no_join_member

    def _misses_join_condition(self, source: SavingConditionSourceVO) -> bool:
        if source.join_restriction is JoinRestriction.ANYONE:
            return False

        if self.eligibility.conditions:
            return False

        for item in self.other_eligibility_conditions:
            if item.value == source.join_member:
                return False

        return True

    def _misses_bonus_condition(self, source: SavingConditionSourceVO) -> bool:
        if self.bonus_status is not BonusConditionStatus.UNKNOWN:
            return False

        if self.bonuses:
            return False

        has_bonus_text: bool = bool(source.spcl_cnd)
        has_rate_gap: bool = source.max_bonus_point > 0
        return has_bonus_text or has_rate_gap

    def _verify_checklists(self, source: SavingConditionSourceVO) -> None:
        """체크리스트로 보여 줄 문장도 공시 원문에서 가져온 것이어야 한다."""
        for item in self.other_eligibility_conditions:
            found_in_source: bool = item.value in source.join_member or item.value in source.etc_note
            if not item.value.strip() or not found_in_source:
                raise ConditionVerificationError("자격요건 체크리스트의 근거가 가입대상·유의사항 원문에 없습니다")

        for item in self.other_bonus_conditions:
            found_in_source = item.value in source.spcl_cnd or item.value in source.etc_note
            if not item.value.strip() or not found_in_source:
                raise ConditionVerificationError("우대사항 체크리스트의 근거가 우대조건·유의사항 원문에 없습니다")

    def _verify_bonus_status(self, source: SavingConditionSourceVO) -> None:
        if self.bonus_status is BonusConditionStatus.NO_BONUS:
            self._verify_no_bonus(source)
            return

        if self.bonus_status is BonusConditionStatus.AVAILABLE:
            if not self.bonuses:
                raise ConditionVerificationError("우대금리 있음 상태인데 조건이 비어 있습니다")
            if self.unresolved:
                raise ConditionVerificationError("우대금리 추출 완료 상태에 미해석 조건이 남아 있습니다")
            return

        if self.bonus_status is BonusConditionStatus.CHECKLIST:
            if not self.other_bonus_conditions:
                raise ConditionVerificationError("체크리스트 상태에는 확인할 우대사항 원문이 필요합니다")

    def _verify_no_bonus(self, source: SavingConditionSourceVO) -> None:
        if self.bonuses or self.unresolved or self.other_bonus_conditions:
            raise ConditionVerificationError("우대금리 없음 상태와 공시 금리가 일치하지 않습니다")

        if source.max_bonus_point > 0:
            raise ConditionVerificationError("우대금리 없음 상태와 공시 금리가 일치하지 않습니다")

        if not SavingConditionSourceVO.declares_no_bonus(source.spcl_cnd):
            raise ConditionVerificationError("우대금리 없음 근거가 공시 원문에 없습니다")

