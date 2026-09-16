from __future__ import annotations
from time import perf_counter
from typing import TYPE_CHECKING
from infra.request_context import current_request_id, short_request_id
from app.dto.response.saving_refresh import SavingRefreshResponseDTO
from app.exception.saving import SavingBackupError

if TYPE_CHECKING:
    from logging import Logger

    from app.dto.response.saving_refresh import (
        BonusStructureResponseDTO, DisclosureSyncResponseDTO
    )
    from app.source.banks_source import BanksSource
    from app.source.questions_source import QuestionsSource
    from app.service.saving.bonus_structure import BonusStructureService
    from app.service.saving.disclosure_sync import DisclosureSyncService
    from app.source.saving_products_source import SavingProductsSource
    from infra.sqlite_backup import SqliteBackup


class SavingRefreshService:
    """
    관리자가 상품을 갱신한다 — 공시 수집부터 필수·우대조건 구조화까지 한 번에 돈다.

    두 배치를 순서대로 부른다. 적재가 먼저인 이유는 원문이 바뀐 상품의 기존 조건을
    적재 단계가 비워 주기 때문이다 — 그래야 구조화가 그 상품을 다시 번역한다.
    """

    _disclosure_sync_service: DisclosureSyncService
    _bonus_structure_service: BonusStructureService
    _savings_source: SavingProductsSource
    _bank_service: BanksSource
    _questions_service: QuestionsSource
    _db_backup: SqliteBackup
    _logger: Logger

    def __init__(
            self,
            disclosure_sync_service: DisclosureSyncService,
            bonus_structure_service: BonusStructureService,
            savings_source: SavingProductsSource,
            bank_service: BanksSource,
            questions_service: QuestionsSource,
            db_backup: SqliteBackup,
            logger: Logger,
    ) -> None:
        self._disclosure_sync_service = disclosure_sync_service
        self._bonus_structure_service = bonus_structure_service
        self._savings_source = savings_source
        self._bank_service = bank_service
        self._questions_service = questions_service
        self._db_backup = db_backup
        self._logger = logger

    async def refresh(self) -> SavingRefreshResponseDTO:
        started_at: float = perf_counter()
        request_id: str = current_request_id()
        self._logger.info("상품 갱신 시작 | req=%s", short_request_id(request_id))

        # 갱신은 DB 를 새로 쓰는 작업이라, 백업 없이는 시작하지 않는다.
        try:
            backup_path: str = await self._db_backup.create()
        except Exception as error:
            self._logger.exception(
                "상품 갱신 종료 | req=%s | 결과=백업실패 | 오류=%s | 소요_ms=%.1f",
                short_request_id(request_id), type(error).__name__, (perf_counter() - started_at) * 1000,
            )
            raise SavingBackupError("DB 백업에 실패해 상품 갱신을 시작하지 않았습니다.") from error
        self._logger.info("상품 갱신 백업 완료 | req=%s | backup=%s", short_request_id(request_id), backup_path)

        try:
            disclosure: DisclosureSyncResponseDTO = await self._disclosure_sync_service.sync()
            bonus: BonusStructureResponseDTO = await self._bonus_structure_service.structure()
        except Exception as error:
            self._logger.exception(
                "상품 갱신 종료 | req=%s | 결과=실패 | 오류=%s | 소요_ms=%.1f",
                short_request_id(request_id), type(error).__name__, (perf_counter() - started_at) * 1000,
            )
            raise

        # 공시 적재는 은행도 함께 새로 넣는다. 셋 다 비워야 갱신 결과가 바로 보인다.
        self._savings_source.clear()
        self._bank_service.clear()
        self._questions_service.clear()
        self._logger.info(
            "상품 갱신 종료 | req=%s | 결과=성공 | 상품=%d | 구조화=%d | 구조화실패=%d | 소요_ms=%.1f",
            short_request_id(request_id), disclosure.products, bonus.structured_savings, bonus.not_structurable_savings,
            (perf_counter() - started_at) * 1000,
        )
        return SavingRefreshResponseDTO(disclosure=disclosure, bonus=bonus)
