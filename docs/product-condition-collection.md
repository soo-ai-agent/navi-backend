# 상품 수집과 조건 추출

`POST /api/v1/admin/products/refresh` 또는 `python -m scripts.sync_disclosure`는
공시 수집·정제·저장 후 모든 저장 상품의 필수 가입조건과 우대조건을 추출한다.
`DisclosureSyncService.sync()`를 직접 호출하면 공시 적재와 이전 조건 무효화까지만 수행한다.

조건 테이블은 개발 환경 시작과 수집 배치의 `create_all` 초기화 경로에서 만들어진다.
배치 실행에는 기존 `DISCLOSURE_*`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` 설정을 사용한다.

## 저장되는 데이터

`product`에는 공시 원문과 가입 제한 분류·월 납입 한도를, `rate_option`에는 기간별 금리를 저장한다.
정형 필드는 코드로 변환한다. LLM이 이 값들을 다시 해석해 덮어쓰지 않는다.

`product_condition`은 상품당 한 행이며 다음을 보관한다.

| 필드 | 의미 |
|---|---|
| `source_json` | 추출 당시 상품명·가입대상·가입방법·우대원문·유의사항과 정형 한도·기간·우대폭 |
| `source_hash` | 위 입력 전체의 SHA-256 |
| `schema_version` | 저장된 조건의 판정 의미·구조를 바꾸는 비호환 변경 시 올리는 추출 규칙 버전 |
| `conditions_json` | `eligibility`, `bonuses`, `unresolved`, 자격·우대 체크리스트를 담은 검증된 JSON |
| `status` | `PENDING`, `EXTRACTED`, `NEEDS_REVIEW`, `FAILED` |
| `review_reason` | 확인 필요·실패 사유 또는 직접 작성 출처 |

조건은 `field`, `operator`, `values`, `source_field`, `source_text`로 표현한다.
`all`/`any` 그룹으로 AND/OR를 보존하고, 나이 범위는 `between`의 두 정수로 저장한다.
지원 필드·연산자는 `app/enums/product_condition.py`, 검증 모델은
`app/model/vo/product_conditions_vo.py`에 있다. 조건 원문을 실행 코드로 바꾸거나 실행하지 않는다.

신뢰 경계에서 타입·필드·연산자·값 범위·중첩 깊이·근거 원문 일치·우대금리 상한을 검증한다.
실패한 AI 응답은 `conditions_json`에 넣지 않는다. 대신 공시 원문으로 만든 체크리스트를 저장한다.
검증 전 응답은 `product_condition_attempt.raw_response`에 그대로 보관하며 성공·실패와 상세 사유를 별도로 기록한다.
응답을 받지 못한 연결·대기 오류는 원문을 만들지 않고 빈 `raw_response`와 실패 사유를 남긴다.
검증은 추출된 의미의 정확성이나 누락 없음을 보장하지 않으므로 `EXTRACTED`는 사람 검수 완료를 뜻하지 않는다.

## 변경과 재시도

변경 대상의 전체 페이지를 읽어 모든 상품의 가입대상·유의사항·우대조건 원문을 먼저 체크리스트로 저장한다.
그 뒤 상품별 LLM을 순차 호출한다. 첫 응답이 오래 걸리거나 배치가 중단되어도 나머지 상품의 원문은 DB에 남는다.
사용자가 요청한 무제한 응답 대기를 유지하며 자동 재시도 루프는 두지 않는다.

정상 응답은 숫자 문자열·true/false 문자열만 외부 JSON 경계에서 정확한 타입으로 복원하고 VO로 검증한다.
체크리스트가 있으면 `CHECKLIST`, 우대 원문이 없고 공시 우대폭도 0이면 `NO_BONUS`로 상태를 명시한다.
표현 불가 항목은 원문과 확인 사유로 보존한다. 정의되지 않은 조건을 AND/OR에서 삭제하면 판정이 달라지므로
해당 응답은 자동 판정에 사용하지 않고 전체 공시 체크리스트로 대체한다. 원래 AI 응답은 실패 시도 기록에 남는다.

JSON·타입·근거·우대 상한 검증 실패나 AI 통신 오류에는 원문 체크리스트를 유지한다.
미해석 조건이 남은 응답도 공통 조건 누락으로 우대가 과다 적용되지 않도록 자동 우대금리를 모두 비운 원문 체크리스트로 저장한다.
가입대상 자체가 비었거나 우대폭은 있는데 우대 원문이 전혀 없으면 `NEEDS_REVIEW`를 유지한다.
체크리스트는 가입 가능 여부를 확정하지 않으며, 확인하지 않은 우대금리를 가산하지 않는다.

가입대상·유의사항·정형 한도 등 추출 입력이나 스키마 버전이 바뀌면 재추출한다.
입력이 같은 `EXTRACTED`/`NEEDS_REVIEW`는 건너뛴다. 명시적으로 조건이 없는 정상 응답도 저장해
매 실행마다 LLM을 다시 부르지 않는다. `FAILED`/`PENDING`은 다음 실행에서 재시도한다.
통신·검증 실패 후 원문 체크리스트로 복구된 `EXTRACTED`도 동일 원문이면 재호출하지 않는다.
체크리스트를 자동 판정 조건으로 보완할 때에는 원문 해시를 검증한 직접 작성 파일을 사용한다.

원문 변경 감지 시 이전 조건과 호환용 우대금리는 무효화한다. LLM 호출은 트랜잭션 밖에서
실행하고, 상품별 최종 조건과 호환용 우대금리는 한 트랜잭션에서 교체한다.
저장 직전 현재 입력 해시를 다시 비교해 추출 중 원문이 바뀐 결과는 버린다.
수집 자체는 기존처럼 단계별 커밋이므로 전체 배치가 하나의 트랜잭션은 아니다.

실패한 상품을 다시 추출하려면 다음 명령을 사용한다.

```bash
python -m scripts.structure_bonuses
```

`NEEDS_REVIEW`는 원문을 확인하고 수정하거나 추출 규칙을 보완한 뒤 버전을 올려 재처리한다.
공식 설명서 자동 조회는 하지 않는다. 응답의 `unresolved` 원본은 시도 기록에 보존하고 추천용 조건은 전체 공시 체크리스트로 대체한다.
현재 필드로 판정할 수 없어 결과에 안내할 항목은 `other_eligibility_conditions`와
`other_bonus_conditions` 체크리스트로 저장한다. 체크리스트는 추천 판정에 사용하지 않는다.

## 외부 LLM 없이 직접 저장

직접 작성 파일은 상품 ID, 검토 당시 `source_hash`, `conditions`를 담는다.
명확한 조건만 자동 판정 규칙으로 작성하고 나머지는 자격요건·우대사항 체크리스트로 보존한다.
시간 초과 30개 상품의 작성본은 `docs/manual-conditions/timeout-part-*.json`에 있다.
나머지 실패·검토 27개의 작성본은 `docs/manual-conditions/remaining-part-*.json`에 있다.

```bash
# 전체 파일을 먼저 검증한다. 이 명령은 DB를 변경하지 않는다.
python -m scripts.import_manual_conditions docs/manual-conditions/timeout-part-*.json

# 검증 후 SQLite 백업을 만들고 상품별 트랜잭션으로 저장한다.
python -m scripts.import_manual_conditions docs/manual-conditions/timeout-part-*.json --apply
```

`--apply`도 전체 파일의 자료형·원문 해시·근거·금리 상한을 먼저 검증한다.
백업은 DB 옆 `backups/`에 생성하며, 저장 직전에도 기존 `ProductService.save_conditions`가
원문 변경 여부를 확인한다. 중간에 원문이 바뀌면 해당 상품부터 중단하며 앞서 완료한 상품은 로그로 확인한다.
`review_reason`에는 직접 작성(Codex)임을 기록하고, 외부 LLM 원문 시도 기록과 섞지 않는다.

미판정 우대가 남아 있으면 `bonus_status=CHECKLIST`로 저장한다. 이 상태는 실제 우대 원문이
체크리스트에 있어야 하며 자격·우대 체크리스트의 근거도 검사한다. `UNKNOWN`이나
`unresolved`의 상태만 바꾸지 않고 검증 가능한 원문을 별도 작성한다. 우대가 실제로 없을 때만 `NO_BONUS`를 쓴다.
가입 제한이 있는데 자동 가입조건이 비어 있다면 가입대상 원문 전체가 자격요건 체크리스트에 있어야 한다.

체크리스트까지 보존한 데이터는 `EXTRACTED`로 읽을 수 있지만, 사용자의 가입 가능 여부나
체크리스트 우대금리 충족이 확정된 것은 아니다. 결과에서 가입조건 확인 필요를 안내하고
미판정 우대금리는 적용 금리에 더하지 않는다. 저장 후 실행 중인 모든 웹 워커를 재시작하면
새 코드와 DB 결과가 즉시 반영된다. 이후 원문이 바뀌면 직접 작성한 결과도 다시 검토해야 한다.

## 질문과 추천에 연결

`POST /api/v1/questions/next`는 저장된 `product_condition`의 필수조건과 복합 우대조건을
코드로 판정한다. 추천 요청에서는 LLM을 호출하지 않는다.

1. 기간을 받은 뒤 상품별 필수조건을 먼저 판정한다. 필요한 답이 없으면 그 질문을 반환한다.
2. 자동 판정 필수조건을 충족한 상품을 후보로 둔다. 자격요건 체크리스트가 남은 상품은 가입 전 확인이 필요하다. 건너뛰거나 잘못 입력한 답은 충족으로 간주하지 않는다.
3. 우대조건은 AND/OR 관계를 그대로 판정하고 충족한 항목을 한 번씩 더한다. 모르는 우대는 더하지 않는다.
4. 모르는 우대가 현재 1위 금리를 넘어설 수 있으면 다음 질문으로 선택한다. 최종 금리는 옵션별 공시 상한을 넘지 않는다.

원문 해시·스키마 버전이 일치하는 `EXTRACTED`만 사용한다. 조건 행이 없는 상품, 대기, 실패,
검토 필요, 오래된 조건, 검증되지 않는 JSON은 추천 후보에서 제외한다.
은행별 거래 유무·급여·카드 사용·카드 사용액은 해당 은행에 대한 답을 따로 받는다.
예를 들어 `existing_bank:0010001`에는 `yes`/`no`로 답한다. 다른 은행에 거래한다는 답만으로
이 은행의 신규 고객이라고 판단하지 않는다.

질문·결과 응답 모양은 유지한다. 클라이언트는 받은 `question.key`를 답 JSON의 키로 그대로 사용한다.
`POST /api/v1/questions/next`는 매번 누적된 답 전체를 받으며 서버에 이전 답을 저장하지 않는다.
빈 답으로 시작해 응답의 질문에 대한 답을 추가하고 다시 호출한다. 답을 수정할 때도 수정된 전체 답을 보낸다.
답은 문자열 또는 `null`이며, 숫자 질문도 숫자를 담은 문자열로 보낸다. 고객 구분은
`individual`/`business` 선택지를 사용한다. HTTP 경계에서 검증한 답은 내부의 불변 `AnswersVO`로 전달한다.
`AnswerVO.status`는 제공된 답을 `PROVIDED`, 명시적 건너뛰기를 `SKIPPED`로 구분한다.
`AnswersVO.value_of()`는 키가 없으면 `UNANSWERED`, 건너뛰었으면 `SKIPPED`를 반환한다.
`ConditionAnswerVO`는 숫자·문자·참거짓 답을 `number_value()`·`text_value()`·`boolean_value()`로 나누어 처리한다.
각 메서드는 해당 자료형의 값 또는 상태만 반환하며, 조건에 맞지 않는 답은 `INVALID`로 반환한다.
이 상태들을 실제 값 `0`·`False`와 구분하며, 내부 답변 판정에는 null을 사용하지 않는다.
기존 HTTP 요청의 null은 클라이언트 호환을 위해 건너뛰기 입력으로만 허용한다.

월 예산보다 상품 월 한도가 작으면 한도까지만 납입하는 기존 동작을 유지한다.
`Product.planned_monthly_deposit()`가 상품별 납입액을 계산하고 월 금액 조건은 이 금액으로 판정한다.
따라서 한도가 낮다는 이유만으로 상품을 제외하지 않는다. 기간 조건은 현재 비교 중인 금리 옵션으로 판정한다.

`QuestionFlowService`가 조회부터 필수조건 확인·우대 판정·정렬·다음 질문 선택까지 순서대로 조립한다.
`AllSavings`는 조회된 상품 묶음과 기간·은행 조회만 맡고, 조건 모델은 검증과 판정,
`ProductRate`는 금리 계산만 담당한다. 질문 문구·선택지는 `QuestionResponseDTO`에서 만들고,
구형 우대조건 변환은 `ProductBonus`에서 담당한다. 조건 추출 I/O는
`app/external/llm/condition_parser.py`에 있다.
캐시는 모든 상품 페이지를 읽으며 기존 10분 TTL을 유지한다. 별도 배치의 갱신은 캐시 만료 후 반영된다.

`product_bonus`에는 기존 형식으로 표현할 수 있는 단일 조건만 호환 저장한다.
추천은 이 호환 목록을 읽지 않고 전체 조건 JSON을 사용하므로 복합조건이 축약되지 않는다.
`GET /api/v1/admin/banks/raw`와 `POST /api/v1/admin/bonus-parse` 및 전용 코드는 제거했다.

갱신 응답은 기존 `disclosure`/`bonus` 필드 구조를 유지한다.
`bonus.scanned_products`는 전체 검사 상품 수, `structured_products`는 원문 체크리스트 복구를 포함한 비교용 조건 저장 완료 수,
`not_structurable_products`는 확인 필요·실패·저장 전 원문 변경 수다.
`created_bonuses`는 호환용 `product_bonus` 저장 수이며 전체 추출 우대조건 수와 다를 수 있다.

## 검증

```bash
python -m unittest discover test
```

외부 API 대신 가짜 LLM 응답을 사용한다. SQLite 통합 테스트로 상태 저장, 조건 동시 저장,
입력 변경 무효화, AI 대기·실패 중 원문 보존, 동일 원문 재호출 방지, 페이지 순회, 오래된 결과 거부와 트랜잭션 롤백을 검증한다.
추천 테스트는 필수조건 제외, AND/OR와 범위 판정, 은행별 답변, 다음 질문 선택, 금리 상한을 검증한다.

## 모델 구분과 의존성

`database/` 밖의 파일이 모두 VO는 아니다. 값으로 비교하고 불변 값만 보관하는 모델은
파일명에 `_vo`, 클래스명에 `VO`를 붙인다.

- `answers_vo.py`: `AnswerVO`, `AnswersVO`
- `condition_context_vo.py`: `ConditionContextVO`
- `condition_answer_vo.py`: `ConditionAnswerVO`
- `checked_bonus_vo.py`: `CheckedBonusVO`
- `product_conditions_vo.py`: 조건·근거·추출 결과·원문 스냅샷 VO

`AllSavings`와 `ProductRate`는 엔티티를 참조하는 조회·계산 보조 모델이므로 VO로 표시하지 않는다.
조건 평가에는 엔티티 대신 `ConditionContextVO`를 전달한다. 원문 스냅샷도
`Product.condition_source()`에서 만들기 때문에 VO가 엔티티를 참조하지 않는다.

VO의 애플리케이션 내부 의존은 `VO → VO·enum` 방향으로만 허용한다.
`test/model/test_vo_dependencies.py`가 DTO·서비스·DAO·엔티티에 대한 역참조를 검사한다.
DB 모델 사이의 양방향 ORM 관계는 연관관계 선언이며 VO 의존성에 포함하지 않는다.

추천에 사용할 추출 결과가 없으면 `ConditionStatus`, 다음 질문이 없으면
`NextStepStatus.DONE`으로 표현한다. 공시의 한도 없음, DB 조회 부재와 nullable 관계,
기존 응답의 선택적 필드는 기존 계약에 따라 null을 유지하며 선언부에 이유를 적는다.
