from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from infra.request_context import current_request_id, short_request_id
from app.constants.seed_question import SEED_QUESTIONS
from app.dto.response.saving_refresh import BonusStructureResponseDTO
from app.enums.saving_condition import ConditionStatus
from app.external.llm.exception import ConditionExtractionError, ConditionLlmParseError
from app.model.database.saving_bonus import SavingBonus
from app.model.database.saving_condition import SavingCondition
from app.model.database.saving_condition_attempt import SavingConditionAttempt
from app.model.database.question import Question
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO

if TYPE_CHECKING:
    from logging import Logger

    from app.model.database.saving import Saving
    from app.service.question.question import QuestionService
    from app.external.llm.condition_parser import ConditionLlmParser
    from app.service.saving.saving import SavingService


@dataclass
class _StructureTally:
    scanned: int = 0

    structured: int = 0

    created_bonuses: int = 0
    """구형 판정기와 호환되게 저장한 우대조건 건수"""

    not_structurable: int = 0
    """확인이 필요하거나 저장하지 못한 상품 수"""

    skipped: int = 0

    def to_response(self) -> BonusStructureResponseDTO:
        return BonusStructureResponseDTO(
            scanned_savings=self.scanned, structured_savings=self.structured,
            created_bonuses=self.created_bonuses,
            not_structurable_savings=self.not_structurable, skipped_savings=self.skipped,
        )


class BonusStructureService:
    _saving_service: SavingService
    _question_service: QuestionService
    _condition_llm_parser: ConditionLlmParser
    _logger: Logger

    def __init__(
            self,
            saving_service: SavingService,
            question_service: QuestionService,
            condition_llm_parser: ConditionLlmParser,
            logger: Logger,
    ) -> None:
        self._saving_service = saving_service
        self._question_service = question_service
        self._condition_llm_parser = condition_llm_parser
        self._logger = logger

    async def structure(self) -> BonusStructureResponseDTO:
        """
        상품 전체의 조건을 구조화한다. 두 단계로 나눠 돈다.

        먼저 모든 상품의 공시 원문을 체크리스트로 저장한다 — AI 응답을 기다리는 동안에도
        사용자가 원문을 볼 수 있어야 하기 때문이다. 그다음 상품마다 AI 에게 번역을 맡긴다.
        """
        await self._question_service.save_missing(SEED_QUESTIONS)
        questions: Sequence[Question] = await self._question_service.list_all()

        tally: _StructureTally = _StructureTally()
        pending_sources: list[SavingConditionSourceVO] = await self._save_checklists(tally)

        for source in pending_sources:
            await self._extract_one(source, questions, tally)

        self._logger.info(
            "조건 추출 완료 | req=%s | 대상=%d | 추출=%d | 확인필요_실패=%d | 건너뜀=%d",
            short_request_id(), tally.scanned, tally.structured, tally.not_structurable, tally.skipped,
        )
        return tally.to_response()

    async def _save_checklists(self, tally: _StructureTally) -> list[SavingConditionSourceVO]:
        """
        1단계 — 모든 상품의 공시 원문을 체크리스트로 먼저 저장한다.

        AI 에게 물어볼 상품의 원문 목록을 돌려준다.
        """
        pending_sources: list[SavingConditionSourceVO] = []
        for saving in await self._saving_service.list_every():
            tally.scanned += 1
            source: SavingConditionSourceVO = saving.condition_source()

            # 최초 수집 상품에는 조건 행이 없어 조회 경계에서만 None 을 사용한다.
            previous: SavingCondition | None = saving.condition
            if previous is not None and previous.can_skip(source):
                tally.skipped += 1
                continue

            checklist: SavingCondition = SavingCondition.from_checklist(
                source, "AI 자동 판정 조건 추출 전 공시 원문을 체크리스트로 저장했습니다."
            )
            if not await self._saving_service.save_conditions(checklist, ()):
                tally.not_structurable += 1
                continue

            pending_sources.append(source)

        return pending_sources

    async def _extract_one(
            self, source: SavingConditionSourceVO, questions: Sequence[Question], tally: _StructureTally,
    ) -> None:
        record: SavingCondition = await self._ask_ai(source)

        extracted: ExtractedConditionsVO | ConditionStatus = record.read_verified(source)
        bonuses: list[SavingBonus] = []
        if isinstance(extracted, ExtractedConditionsVO):
            bonuses = SavingBonus.from_conditions(source.product_id, extracted, questions)

        if not await self._saving_service.save_conditions(record, bonuses):
            tally.not_structurable += 1
            return

        tally.created_bonuses += len(bonuses)
        if record.status is ConditionStatus.NEEDS_REVIEW:
            tally.not_structurable += 1
        else:
            tally.structured += 1

        self._logger.debug(
            "조건 저장 완료 | req=%s | product_id=%s | 상태=%s | 자동우대수=%d | 처리사유=%s",
            short_request_id(), source.product_id, record.status.value, len(bonuses), record.review_reason,
        )

    async def _ask_ai(self, source: SavingConditionSourceVO) -> SavingCondition:
        try:
            parsed = await self._condition_llm_parser.parse(source)
        except Exception as error:
            return await self._record_failure(source, error)

        await self._saving_service.save_condition_attempt(
            SavingConditionAttempt.validated(source, parsed.raw_response)
        )
        return SavingCondition.from_extracted(source, parsed.extracted)

    async def _record_failure(self, source: SavingConditionSourceVO, error: Exception) -> SavingCondition:
        failure: ConditionExtractionError = ConditionExtractionError.from_error(error)
        self._logger.error("조건 추출 실패 | req=%s | product_id=%s | 사유=%s", short_request_id(), source.product_id, failure)

        raw_response: str = ""
        if isinstance(error, ConditionLlmParseError):
            raw_response = error.raw_response

        await self._saving_service.save_condition_attempt(
            SavingConditionAttempt.failed(source, raw_response, str(failure))
        )
        return SavingCondition.from_checklist(source, f"{failure} 공시 원문 체크리스트로 저장했습니다.")
