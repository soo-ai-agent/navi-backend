from __future__ import annotations

import asyncio
import logging
import json
from datetime import date
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch
from unittest.mock import AsyncMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.dao.saving import SavingDao
from app.dao.bank import BankDao
from app.dao.question import QuestionDao
from app.dto.response.saving_refresh import BonusStructureResponseDTO
from app.dto.response.next_step import NextStepResponseDTO
from app.enums.saving_condition import BonusConditionStatus, ConditionAttemptStatus, ConditionStatus
from app.enums.saving import InterestCalcType, JoinRestriction, ReserveType
from app.external.disclosure import Companies, Company, SavingProduct, SavingProductOption, SavingProducts
from app.external.disclosure.code import ReserveType as DisclosureReserveType, InterestType
from app.model.database.bank import Bank
from app.model.database.base import Base
from app.model.database.saving import Saving
from app.model.database.saving_bonus import SavingBonus
from app.model.database.saving_condition import SavingCondition
from app.model.database.saving_condition_attempt import SavingConditionAttempt
from app.model.database.rate_option import RateOption
from app.model.vo.banks_vo import BanksVO
from app.model.vo.questions_vo import QuestionsVO
from app.model.vo.saving_products_vo import SavingProductsVO
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO
from app.service.question.question import QuestionService
from app.service.question.question_flow import QuestionFlowService
from infra.cache.banks import BanksCache
from infra.cache.questions import QuestionsCache
from infra.cache.saving_products import SavingProductsCache
from app.service.saving.bonus_structure import BonusStructureService
from app.external.llm.condition_parser import ConditionLlmParser
from app.external.llm import ChatMessage, LlmClient
from app.service.saving.saving import SavingService
from app.service.saving.disclosure_sync import DisclosureSyncService
from app.service.bank.bank import BankService
from test.service.saving.saving_fixture import answers


class FakeLlm:
    def __init__(self) -> None:
        self.fail = False
        self.calls = 0
        self.response = {
            "eligibility": {"match": "all", "conditions": []},
            "bonuses": [], "unresolved": [],
        }

    async def ask_json(self, messages, **_options):
        self.calls += 1
        if self.fail:
            raise TimeoutError("test timeout")
        return json.dumps(self.response)


def saving(product_id: str = "bank:P1") -> Saving:
    return Saving(
        product_id=product_id, bank_code="bank", name="적금", join_member="누구나",
        join_restriction=JoinRestriction.ANYONE, join_ways="앱", monthly_limit=500000,
        bonus_condition_text="", bonus_source_hash="old", after_maturity_rate_text="",
        etc_note="", disclosure_month="2026-09", disclosure_start_date=date(2026, 9, 1),
        rate_options=[RateOption(
            saving_term_months=12, reserve_type=ReserveType.FREE,
            interest_calc_type=InterestCalcType.SIMPLE, base_rate=Decimal("3"), max_rate=Decimal("3"),
        )],
    )


def disclosure_client() -> AsyncMock:
    client = AsyncMock()
    client.get_companies.return_value = Companies(companies=(Company(
        fin_co_no="bank", kor_co_nm="은행", homp_url="", cal_tel=""
    ),))
    # 날짜와 가입 제한 코드는 공시 JSON 입력 그대로 검증한다.
    client.get_saving_products.return_value = SavingProducts(
        products=(SavingProduct.model_validate({
            "dcls_month": "202609", "fin_co_no": "bank", "fin_prdt_cd": "P1", "kor_co_nm": "은행",
            "fin_prdt_nm": "적금", "join_way": "앱", "join_member": "만 19세 이상", "join_deny": "3",
            "spcl_cnd": "급여이체 시 0.7%p", "mtrt_int": "", "etc_note": "", "max_limit": 500000,
            "dcls_strt_day": "20260901",
        }),),
        options=(SavingProductOption(
            fin_co_no="bank", fin_prdt_cd="P1", save_trm=12, rsrv_type=DisclosureReserveType.FREE,
            intr_rate_type=InterestType.SIMPLE, intr_rate=3, intr_rate2=3.7,
        ),),
    )
    return client


class TestConditionStructureIntegration(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with self.sessions() as session, session.begin():
            session.add(Bank(bank_code="bank", original_name="은행", display_name="은행", homepage_url="", call_center=""))
            session.add(saving())
        self.products = SavingService(self.sessions, SavingDao())
        self.llm = FakeLlm()
        llm_client = AsyncMock(spec=LlmClient)
        llm_client.ask_json.side_effect = self.llm.ask_json
        self.llm_client: AsyncMock = llm_client
        self.service = BonusStructureService(
            self.products, QuestionService(self.sessions, QuestionDao()),
            ConditionLlmParser(llm_client), logging.getLogger("test.conditions"),
        )

    async def read_condition(self, product_id: str) -> SavingCondition | None:
        async with self.sessions() as session:
            return await session.get(SavingCondition, product_id)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_빈_조건도_완료로_저장하고_재호출하지_않는다(self):
        await self.service.structure()
        result = await self.service.structure()
        record = await self.read_condition("bank:P1")
        assert record is not None

        self.assertEqual(ConditionStatus.EXTRACTED, record.status)
        conditions = ExtractedConditionsVO.model_validate_json(record.conditions_json)
        self.assertEqual((), conditions.bonuses)
        self.assertEqual(BonusConditionStatus.NO_BONUS, conditions.bonus_status)
        self.assertEqual(1, result.skipped_savings)
        self.assertEqual(1, self.llm.calls)

    async def test_필수조건과_우대조건을_함께_저장한다(self):
        async with self.sessions() as session, session.begin():
            saved = await session.get(Saving, "bank:P1")
            assert saved is not None
            saved.join_member = "만 19~34세 개인"
            saved.bonus_condition_text = "급여이체 시 0.7%p"
            rate = await session.scalar(select(RateOption))
            assert rate is not None
            rate.max_rate = Decimal("3.7")
        self.llm.response = {
            "eligibility": {"match": "all", "conditions": [
                {"field": "age", "operator": "between", "values": [19, 34],
                 "source_field": "join_member", "source_text": "만 19~34세 개인"},
            ]},
            "bonuses": [{"label": "급여이체", "percentage_point": "0.7", "condition": {
                "match": "all", "conditions": [
                    {"field": "salary_bank", "operator": "eq", "values": ["PRODUCT_BANK"],
                     "source_field": "spcl_cnd", "source_text": "급여이체 시 0.7%p"},
                ],
            }}],
            "unresolved": [],
        }
        result = await self.service.structure()
        record = await self.read_condition("bank:P1")
        assert record is not None
        conditions = ExtractedConditionsVO.model_validate_json(record.conditions_json)

        self.assertEqual((19, 34), conditions.eligibility.predicates()[0].values)
        self.assertEqual(1, result.created_bonuses)
        async with self.sessions() as session:
            bonus = await session.scalar(select(SavingBonus))
            assert bonus is not None
            self.assertEqual("salaryBank", bonus.answer_code)
            self.assertEqual(Decimal("0.7"), bonus.percentage_point)

    async def test_근거가_위조된_조건_대신_공시_원문만_저장한다(self) -> None:
        self.llm.response["eligibility"]["conditions"] = [
            {"field": "age", "operator": "gte", "values": [19],
             "source_field": "join_member", "source_text": "공시에 없는 나이 제한"}
        ]
        await self.service.structure()
        record = await self.read_condition("bank:P1")
        assert record is not None

        self.assertEqual(ConditionStatus.EXTRACTED, record.status)
        conditions: ExtractedConditionsVO = ExtractedConditionsVO.model_validate_json(record.conditions_json)
        self.assertEqual((), conditions.eligibility.predicates())
        self.assertEqual("누구나", conditions.other_eligibility_conditions[0].value)
        self.assertNotIn("공시에 없는 나이 제한", record.conditions_json)
        async with self.sessions() as session:
            attempt = await session.scalar(
                select(SavingConditionAttempt).order_by(SavingConditionAttempt.id.desc())
            )
        assert attempt is not None
        self.assertEqual(ConditionAttemptStatus.FAILED, attempt.status)
        self.assertEqual(json.dumps(self.llm.response), attempt.raw_response)
        self.assertIn("근거가 공시 원문에 없습니다", attempt.reason)

    async def test_복합_우대를_단순_우대금리로_바꾸지_않는다(self):
        async with self.sessions() as session, session.begin():
            saved = await session.get(Saving, "bank:P1")
            assert saved is not None
            saved.bonus_condition_text = "급여이체 또는 앱 가입 시 0.7%p"
            rate = await session.scalar(select(RateOption))
            assert rate is not None
            rate.max_rate = Decimal("3.7")
        self.llm.response["bonuses"] = [{
            "label": "급여이체 또는 앱 가입", "percentage_point": "0.7",
            "condition": {"match": "any", "conditions": [
                {"field": "salary_bank", "operator": "eq", "values": ["PRODUCT_BANK"],
                 "source_field": "spcl_cnd", "source_text": "급여이체 또는 앱 가입 시 0.7%p"},
                {"field": "mobile", "operator": "eq", "values": [True],
                 "source_field": "spcl_cnd", "source_text": "급여이체 또는 앱 가입 시 0.7%p"},
            ]},
        }]
        result = await self.service.structure()
        record = await self.read_condition("bank:P1")
        assert record is not None
        extracted = ExtractedConditionsVO.model_validate_json(record.conditions_json)

        self.assertEqual("any", extracted.bonuses[0].condition.match)
        self.assertEqual(2, len(extracted.bonuses[0].condition.conditions))
        self.assertEqual(0, result.created_bonuses)
        async with self.sessions() as session:
            self.assertIsNone(await session.scalar(select(SavingBonus)))

    async def test_공시_갱신은_기존_집계를_유지하며_조건을_무효화한다(self):
        await self.service.structure()
        async with self.sessions() as session, session.begin():
            session.add(SavingBonus(
                product_id="bank:P1", answer_code="salaryBank", percentage_point=Decimal("0.7"), label="기존 우대"
            ))
        client = disclosure_client()
        sync = DisclosureSyncService(
            client, self.products, BankService(self.sessions, BankDao()), logging.getLogger("test.sync")
        )
        first = await sync.sync()
        second = await sync.sync()

        self.assertEqual(1, first.bonus_reset_savings)
        self.assertEqual(0, second.bonus_reset_savings)
        record = await self.read_condition("bank:P1")
        assert record is not None
        self.assertEqual(ConditionStatus.PENDING, record.status)
        async with self.sessions() as session:
            self.assertIsNone(await session.scalar(select(SavingBonus)))

    async def test_우대폭이_있는데_근거가_없으면_확인_필요다(self):
        async with self.sessions() as session, session.begin():
            rate = await session.scalar(select(RateOption))
            assert rate is not None
            rate.max_rate = Decimal("3.7")
        await self.service.structure()

        record = await self.read_condition("bank:P1")
        assert record is not None
        self.assertEqual(ConditionStatus.NEEDS_REVIEW, record.status)

    async def test_미해석_공통조건이_있는_우대는_기존_금리에_가산하지_않는다(self):
        async with self.sessions() as session, session.begin():
            saved = await session.get(Saving, "bank:P1")
            assert saved is not None
            saved.bonus_condition_text = "급여이체 시 0.7%p. 유지기간은 설명서 참조"
            rate = await session.scalar(select(RateOption))
            assert rate is not None
            rate.max_rate = Decimal("3.7")
        self.llm.response = {
            "eligibility": {"match": "all", "conditions": []},
            "bonuses": [{"label": "급여이체", "percentage_point": "0.7", "condition": {
                "match": "all", "conditions": [
                    {"field": "salary_bank", "operator": "eq", "values": ["PRODUCT_BANK"],
                     "source_field": "spcl_cnd", "source_text": "급여이체 시 0.7%p"},
                ],
            }}],
            "unresolved": [{"source_field": "spcl_cnd", "source_text": "유지기간은 설명서 참조",
                            "reason": "급여이체 유지기간 불명"}],
        }
        result = await self.service.structure()
        record = await self.read_condition("bank:P1")
        assert record is not None

        self.assertEqual(ConditionStatus.EXTRACTED, record.status)
        conditions: ExtractedConditionsVO = ExtractedConditionsVO.model_validate_json(record.conditions_json)
        self.assertEqual((), conditions.bonuses)
        self.assertEqual(BonusConditionStatus.CHECKLIST, conditions.bonus_status)
        self.assertEqual("급여이체 시 0.7%p. 유지기간은 설명서 참조", conditions.other_bonus_conditions[0].value)
        self.assertEqual(0, result.created_bonuses)
        async with self.sessions() as session:
            self.assertIsNone(await session.scalar(select(SavingBonus)))

    async def test_AI_시간초과도_원문과_실패_원인을_보존한다(self) -> None:
        self.llm.fail = True
        await self.service.structure()
        record = await self.read_condition("bank:P1")
        assert record is not None
        self.assertEqual(ConditionStatus.EXTRACTED, record.status)
        conditions: ExtractedConditionsVO = ExtractedConditionsVO.model_validate_json(record.conditions_json)
        self.assertEqual("누구나", conditions.other_eligibility_conditions[0].value)
        async with self.sessions() as session:
            attempt = await session.scalar(select(SavingConditionAttempt))
        assert attempt is not None
        self.assertEqual(ConditionAttemptStatus.FAILED, attempt.status)
        self.assertEqual("", attempt.raw_response)
        self.assertIn("응답 대기 시간을 초과", attempt.reason)

    async def test_가입대상_변경은_기존_추출을_무효화한다(self):
        await self.service.structure()
        async with self.sessions() as session, session.begin():
            saved = await session.get(Saving, "bank:P1")
            assert saved is not None
            saved.join_member = "만 19~34세"
            saved.join_restriction = JoinRestriction.PARTIAL
        await self.products.invalidate_changed_conditions()
        record = await self.read_condition("bank:P1")
        assert record is not None
        self.assertEqual(ConditionStatus.PENDING, record.status)

        await self.service.structure()
        record = await self.read_condition("bank:P1")
        assert record is not None
        self.assertEqual(ConditionStatus.EXTRACTED, record.status)
        conditions: ExtractedConditionsVO = ExtractedConditionsVO.model_validate_json(record.conditions_json)
        self.assertEqual("만 19~34세", conditions.other_eligibility_conditions[0].value)
        self.assertEqual((), conditions.eligibility.predicates())

    async def test_유효한_금리가_없어진_상품은_이전_옵션을_남기지_않는다(self):
        await self.products.replace_rate_options((), ("bank:P1",))
        saved = (await self.products.list_all())[0]

        self.assertEqual([], saved.rate_options)

    async def test_추출_중_바뀐_원문에는_이전_결과를_저장하지_않는다(self):
        saved = (await self.products.list_all())[0]
        pending = SavingCondition.pending(saved.condition_source())
        async with self.sessions() as session, session.begin():
            changed = await session.get(Saving, "bank:P1")
            assert changed is not None
            changed.etc_note = "가입대상 변경"

        self.assertFalse(await self.products.save_conditions(pending, ()))
        self.assertIsNone(await self.read_condition("bank:P1"))

    async def test_페이지_상한을_넘는_상품도_추출한다(self):
        async with self.sessions() as session, session.begin():
            session.add(saving("bank:P2"))
        with patch("app.service.saving.saving._LIMIT", 1):
            result = await self.service.structure()

        self.assertEqual(2, result.structured_savings)
        record = await self.read_condition("bank:P2")
        assert record is not None
        self.assertEqual(ConditionStatus.EXTRACTED, record.status)

    async def test_조건_저장_실패는_기존_조건까지_롤백한다(self):
        await self.service.structure()
        saved = (await self.products.list_all())[0]
        pending = SavingCondition.pending(saved.condition_source())
        invalid = SavingBonus(product_id="bank:P1", label="금리 누락")
        from sqlalchemy.exc import IntegrityError
        with self.assertRaises(IntegrityError):
            await self.products.save_conditions(pending, (invalid,))

        record = await self.read_condition("bank:P1")
        assert record is not None
        self.assertEqual(ConditionStatus.EXTRACTED, record.status)
        async with self.sessions() as session:
            self.assertEqual([], list((await session.scalars(select(SavingBonus))).all()))

    async def test_금리_갱신이_실패해도_변경된_상품의_이전_우대는_남지_않는다(self):
        await self.service.structure()
        async with self.sessions() as session, session.begin():
            session.add(SavingBonus(
                product_id="bank:P1", answer_code="salaryBank", percentage_point=Decimal("0.7"), label="이전 우대"
            ))
        client = disclosure_client()
        sync = DisclosureSyncService(
            client, self.products, BankService(self.sessions, BankDao()), logging.getLogger("test.sync")
        )
        with patch.object(self.products, "replace_rate_options", side_effect=RuntimeError("금리 저장 실패")):
            with self.assertRaises(RuntimeError):
                await sync.sync()

        async with self.sessions() as session:
            saved = await session.get(Saving, "bank:P1")
            assert saved is not None
            self.assertEqual("급여이체 시 0.7%p", saved.bonus_condition_text)
            self.assertIsNone(await session.scalar(select(SavingBonus)))

    async def test_저장한_조건을_다음질문과_추천에서_사용한다(self):
        target = (await self.products.list_all())[0]
        target.join_member = "만 19세 이상"
        await self.products.save_all((target,))
        self.llm.response["eligibility"] = {"match": "all", "conditions": [{
            "field": "age", "operator": "gte", "values": [19],
            "source_field": "join_member", "source_text": "만 19세 이상",
        }]}
        await self.service.structure()
        flow = QuestionFlowService(
            SavingProductsCache(self.products, logging.getLogger("test.cache")),
            BanksCache(BankService(self.sessions, BankDao()), logging.getLogger("test.cache")),
            QuestionsCache(QuestionService(self.sessions, QuestionDao()), logging.getLogger("test.cache")),
            logging.getLogger("test.question_flow"),
        )
        step = await flow.next_step(answers(("months", "12")))
        assert step.question is not None
        self.assertEqual("age", step.question.key)

    async def test_추천캐시가_마지막_상품페이지까지_조회한다(self):
        await self.products.save_all((saving("bank:P2"),))
        await self.service.structure()
        savings_cache = SavingProductsCache(
            self.products, logging.getLogger("test.cache"),
        )
        with patch("app.service.saving.saving._LIMIT", 1):
            snapshot = await savings_cache.get()
        self.assertEqual(("bank:P1", "bank:P2"), tuple(row.product_id for row in snapshot.products))
        result = await QuestionFlowService(
            savings_cache,
            BanksCache(BankService(self.sessions, BankDao()), logging.getLogger("test.cache")),
            QuestionsCache(QuestionService(self.sessions, QuestionDao()), logging.getLogger("test.cache")),
            logging.getLogger("test.question_flow"),
        ).next_step(
            answers(("months", "12"))
        )
        assert result.result is not None
        self.assertEqual(("bank:P1", "bank:P2"), tuple(row.product_id for row in result.result.rows))

    async def test_저장한_복합우대를_추천금리에_반영한다(self):
        async with self.sessions() as session, session.begin():
            target = await session.get(Saving, "bank:P1")
            assert target is not None
            target.bonus_condition_text = "급여이체하고 앱으로 가입하면 0.7%p"
            option = await session.scalar(select(RateOption))
            assert option is not None
            option.max_rate = Decimal("3.7")
        self.llm.response["bonuses"] = [{"label": "급여와 앱", "percentage_point": "0.7", "condition": {
            "match": "all", "conditions": [
                {"field": "salary_bank", "operator": "eq", "values": ["PRODUCT_BANK"],
                 "source_field": "spcl_cnd", "source_text": "급여이체하고"},
                {"field": "mobile", "operator": "eq", "values": [True],
                 "source_field": "spcl_cnd", "source_text": "앱으로 가입하면"},
            ],
        }}]
        await self.service.structure()
        savings_cache = AsyncMock(spec=SavingProductsCache)
        savings_cache.get.return_value = SavingProductsVO(tuple(await self.products.list_all()))
        banks_cache = AsyncMock(spec=BanksCache)
        banks_cache.get.return_value = BanksVO((Bank(bank_code="bank", display_name="은행"),))
        questions_cache = AsyncMock(spec=QuestionsCache)
        questions_cache.get.return_value = QuestionsVO(())
        result = await QuestionFlowService(
            savings_cache, banks_cache, questions_cache, logging.getLogger("test.question_flow"),
        ).next_step(
            answers(("months", "12"), ("salary_bank", "bank"), ("mobile", "yes"))
        )
        assert result.result is not None
        self.assertEqual(Decimal("3.7"), result.result.rows[0].rate)
        self.assertEqual(1, len(result.result.rows[0].bonus_results))

    async def test_첫_AI_응답을_기다리기_전에_모든_상품_원문을_저장한다(self) -> None:
        await self.products.save_all((saving("bank:P2"),))
        started: asyncio.Event = asyncio.Event()
        release: asyncio.Event = asyncio.Event()

        async def wait_for_response(messages: tuple[ChatMessage, ...], **_options: object) -> str:
            started.set()
            await release.wait()
            return json.dumps(self.llm.response)

        self.llm_client.ask_json.side_effect = wait_for_response
        task: asyncio.Task[BonusStructureResponseDTO] = asyncio.create_task(self.service.structure())
        try:
            # 테스트가 잘못된 순서로 영원히 기다리지 않게 하는 제한이며 실제 LLM 대기 설정과 무관하다.
            await asyncio.wait_for(started.wait(), timeout=2)
            async with self.sessions() as session:
                records: tuple[SavingCondition, ...] = tuple(
                    await session.scalars(select(SavingCondition).order_by(SavingCondition.product_id))
                )
            self.assertEqual(("bank:P1", "bank:P2"), tuple(record.product_id for record in records))
            for record in records:
                with self.subTest(product_id=record.product_id):
                    conditions: ExtractedConditionsVO = ExtractedConditionsVO.model_validate_json(record.conditions_json)
                    self.assertEqual(ConditionStatus.EXTRACTED, record.status)
                    self.assertEqual("누구나", conditions.other_eligibility_conditions[0].value)
        finally:
            release.set()
            await task

    async def test_AI_응답_대기_중에도_저장된_원문으로_추천한다(self) -> None:
        started: asyncio.Event = asyncio.Event()
        release: asyncio.Event = asyncio.Event()

        async def wait_for_response(messages: tuple[ChatMessage, ...], **_options: object) -> str:
            started.set()
            await release.wait()
            return json.dumps(self.llm.response)

        self.llm_client.ask_json.side_effect = wait_for_response
        flow: QuestionFlowService = QuestionFlowService(
            SavingProductsCache(self.products, logging.getLogger("test.cache")),
            BanksCache(BankService(self.sessions, BankDao()), logging.getLogger("test.cache")),
            QuestionsCache(QuestionService(self.sessions, QuestionDao()), logging.getLogger("test.cache")),
            logging.getLogger("test.question_flow"),
        )
        task: asyncio.Task[BonusStructureResponseDTO] = asyncio.create_task(self.service.structure())
        try:
            # 테스트용 대기 감시다. 운영 LLM 요청에는 응답 제한 시간을 추가하지 않는다.
            await asyncio.wait_for(started.wait(), timeout=2)
            result: NextStepResponseDTO = await flow.next_step(answers(("months", "12")))
            assert result.result is not None
            self.assertEqual("bank:P1", result.result.rows[0].product_id)
            self.assertEqual("누구나", result.result.rows[0].other_eligibility_conditions[0].value)
        finally:
            release.set()
            await task

    async def test_잘린_JSON_원문을_기록하고_다음_상품도_처리한다(self) -> None:
        await self.products.save_all((saving("bank:P2"),))
        truncated: str = '{"eligibility": {"match": "all", "conditions": ['
        valid: str = json.dumps(self.llm.response)
        self.llm_client.ask_json.side_effect = (truncated, valid)

        result: BonusStructureResponseDTO = await self.service.structure()

        async with self.sessions() as session:
            attempts: tuple[SavingConditionAttempt, ...] = tuple(
                await session.scalars(select(SavingConditionAttempt).order_by(SavingConditionAttempt.id))
            )
        self.assertEqual(2, result.structured_savings)
        self.assertEqual(
            (("bank:P1", ConditionAttemptStatus.FAILED, truncated), ("bank:P2", ConditionAttemptStatus.VALIDATED, valid)),
            tuple((attempt.product_id, attempt.status, attempt.raw_response) for attempt in attempts),
        )
        self.assertTrue(attempts[0].reason)

    async def test_같은_원문의_수동_완료_조건은_AI로_덮어쓰지_않는다(self) -> None:
        target: Saving = (await self.products.list_all())[0]
        source: SavingConditionSourceVO = target.condition_source()
        manual: SavingCondition = SavingCondition.from_manual(source, ExtractedConditionsVO.from_source_checklist(source))
        await self.products.save_conditions(manual, ())

        result: BonusStructureResponseDTO = await self.service.structure()

        record = await self.read_condition("bank:P1")
        assert record is not None
        self.llm_client.ask_json.assert_not_called()
        self.assertEqual(1, result.skipped_savings)
        self.assertEqual(manual.conditions_json, record.conditions_json)
        self.assertEqual(manual.review_reason, record.review_reason)

    async def test_예전_원문의_AI_실패가_새_원문_조건을_덮어쓰지_않는다(self) -> None:
        async def change_source_and_fail(messages: tuple[ChatMessage, ...], **_options: object) -> str:
            changed: Saving = (await self.products.list_all())[0]
            changed.join_member = "만 30세 이상"
            await self.products.save_all((changed,))
            source: SavingConditionSourceVO = changed.condition_source()
            await self.products.save_conditions(SavingCondition.from_manual(source, ExtractedConditionsVO.from_source_checklist(source)), ())
            raise TimeoutError("test timeout")

        self.llm_client.ask_json.side_effect = change_source_and_fail

        await self.service.structure()

        target: Saving = (await self.products.list_all())[0]
        assert target.condition is not None
        conditions: ExtractedConditionsVO = ExtractedConditionsVO.model_validate_json(target.condition.conditions_json)
        self.assertEqual(target.condition_source().source_hash(), target.condition.source_hash)
        self.assertEqual("만 30세 이상", conditions.other_eligibility_conditions[0].value)
        self.assertIn("직접 작성", target.condition.review_reason)

    async def test_가입대상_원문이_없으면_비교_완료로_저장하지_않는다(self) -> None:
        target: Saving = (await self.products.list_all())[0]
        target.join_member = ""
        await self.products.save_all((target,))

        await self.service.structure()

        record = await self.read_condition("bank:P1")
        assert record is not None
        self.assertEqual(ConditionStatus.NEEDS_REVIEW, record.status)
