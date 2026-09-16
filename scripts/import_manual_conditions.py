from __future__ import annotations
import argparse
import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Sequence
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncEngine
from app.model.database.saving import Saving
from app.model.database.saving_bonus import SavingBonus
from app.model.database.saving_condition import SavingCondition
from app.model.database.question import Question
from app.model.vo.manual_conditions_vo import ManualConditionsVO
from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO
from app.service.saving.saving import SavingService
from bootstrap.container.application import ApplicationConfig
from bootstrap.context import Context
from config import app_config, logger


class ImportArguments(argparse.Namespace):
    files: list[Path]
    apply: bool


async def import_conditions(entries: tuple[ManualConditionsVO, ...], apply: bool) -> None:
    container = ApplicationConfig()
    Context(container, logger, app_config)
    engine: AsyncEngine = container.component.async_sqlalchemy_engine()
    service: SavingService = container.store.saving_service()
    try:
        products: list[Saving] = []
        while True:
            page: Sequence[Saving] = await service.list_all(len(products))
            if not page:
                break
            products.extend(page)

        records: list[SavingCondition] = []
        seen_ids: set[str] = set()
        for entry in entries:
            if entry.product_id in seen_ids:
                raise ValueError(f"중복 상품입니다: {entry.product_id}")
            seen_ids.add(entry.product_id)
            # 파일이 가리키는 상품이 DB에서 삭제되었을 수 있어 조회 경계에서만 None을 사용한다.
            saving: Saving | None = next((item for item in products if item.product_id == entry.product_id), None)
            if saving is None:
                raise ValueError(f"저장 대상 상품이 없습니다: {entry.product_id}")
            source: SavingConditionSourceVO = saving.condition_source()
            entry.verify_source(source)
            records.append(SavingCondition.from_manual(source, entry.conditions))
            logger.info("직접 작성 조건 검증 완료 | product_id=%s | 상품=%s", entry.product_id, source.name)

        if not apply:
            logger.info("직접 작성 조건 검증 완료 | 검증수=%d | 안내=DB 반영은 --apply로 실행", len(records))
            return

        backup: Path = await asyncio.to_thread(backup_database, engine)
        logger.info("직접 저장 전 DB 백업 완료 | backup=%s", backup)
        questions: Sequence[Question] = await container.store.question_service().list_all()
        for entry, record in zip(entries, records, strict=True):
            bonuses: list[SavingBonus] = SavingBonus.from_conditions(entry.product_id, entry.conditions, questions)
            if not await service.save_conditions(record, bonuses):
                raise ValueError(f"저장 직전 공시 원문이 변경되어 중단했습니다: {entry.product_id}")
            logger.info("직접 작성 조건 저장 완료 | product_id=%s", entry.product_id)
        logger.info("직접 작성 조건 저장 완료 | 저장수=%d | LLM호출=0", len(records))
    finally:
        await engine.dispose()


def backup_database(engine: AsyncEngine) -> Path:
    # SQLAlchemy URL은 서버형 DB에서 파일 경로가 없을 수 있어 None을 반환한다.
    database: str | None = engine.url.database
    if engine.url.get_backend_name() != "sqlite" or not database:
        raise ValueError("직접 저장 스크립트의 자동 백업은 SQLite 파일 DB에서만 지원합니다")
    source: Path = Path(database).resolve()
    backup_dir: Path = source.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup: Path = backup_dir / f"before-manual-conditions-{datetime.now():%Y%m%d-%H%M%S-%f}.db"
    with sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True) as original:
        with sqlite3.connect(backup) as destination:
            original.backup(destination)
    return backup


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="공시 원문으로 직접 작성한 조건을 검증·저장합니다")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--apply", action="store_true")
    args: ImportArguments = parser.parse_args(namespace=ImportArguments())
    entries: list[ManualConditionsVO] = []
    adapter: TypeAdapter[tuple[ManualConditionsVO, ...]] = TypeAdapter(tuple[ManualConditionsVO, ...])
    for path in args.files:
        entries.extend(adapter.validate_json(path.read_text(encoding="utf-8")))
    if not entries:
        raise ValueError("직접 작성한 조건 파일이 비어 있습니다")
    asyncio.run(import_conditions(tuple(entries), args.apply))


if __name__ == "__main__":
    main()
