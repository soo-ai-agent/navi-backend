from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import Sequence
from app.enums.saving_condition import ConditionStatus
from app.model.database.saving import Saving
from app.model.database.saving_bonus import SavingBonus
from app.model.database.saving_condition import SavingCondition
from app.model.database.question import Question
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
from app.model.vo.manual_conditions_vo import ManualConditionsVO
from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO
from bootstrap.container.application import ApplicationConfig
from bootstrap.context import Context
from config import app_config, logger as _logger

EXTRACTION_DIR = Path("data/manual-extraction")


async def main() -> None:
    """현재 저장된 조건을 data/manual-extraction/ JSON으로 내보낸다.

    직접 작성한 조건의 정본을 코드가 아닌 검토 파일에 둔다. 내보낸 뒤에는
    scripts/import_manual_conditions.py 가 이 파일들을 다시 적재한다.
    """
    di_container = ApplicationConfig()
    Context(di_container, _logger, app_config=app_config)

    saving_service = di_container.store.saving_service()
    EXTRACTION_DIR.mkdir(parents=True, exist_ok=True)

    exported: int = 0
    try:
        offset: int = 0
        while True:
            products: Sequence[Saving] = await saving_service.list_all(offset)
            if not products:
                break
            offset += len(products)
            for saving in products:
                if saving.condition is None:
                    continue
                source: SavingConditionSourceVO = saving.condition_source()
                stored: ExtractedConditionsVO | ConditionStatus = saving.condition.read_verified(source)
                if not isinstance(stored, ExtractedConditionsVO):
                    continue
                manual = ManualConditionsVO(
                    product_id=saving.product_id, source_hash=source.source_hash(), conditions=stored,
                )
                name: str = saving.product_id.replace(":", "-")
                # import_manual_conditions.py 가 읽는 형식은 ManualConditionsVO 의 배열이다.
                (EXTRACTION_DIR / f"{name}-conditions.json").write_text(
                    json.dumps([json.loads(manual.model_dump_json())], ensure_ascii=False, indent=4) + "\n",
                    encoding="utf-8",
                )
                (EXTRACTION_DIR / f"{name}-source.json").write_text(
                    json.dumps(json.loads(source.model_dump_json()), ensure_ascii=False, indent=4) + "\n",
                    encoding="utf-8",
                )
                exported += 1
    finally:
        await di_container.component.async_sqlalchemy_engine().dispose()

    print(json.dumps({"내보낸_상품": exported, "경로": str(EXTRACTION_DIR)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
