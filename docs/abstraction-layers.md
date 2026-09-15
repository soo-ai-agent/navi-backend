# 추상화 레벨 지도

이 문서는 backend 의 모든 파이썬 파일이 어느 높이에 있는지를 적은 지도다.
새 코드를 어디에 둘지, 지금 보고 있는 파일이 무슨 층인지 판단할 때 본다.
여기 적힌 것은 전부 실제 파일을 읽어 확인한 사실이며, 앞으로 지킬 계획이 아니라 지금의 모습이다.

이름에 쓰는 낱말은 [도메인 어휘 사전](domain-glossary.md)이 정한다.

---

## 1. 추상화 레벨이란 무엇인가

프로그램은 데이터와 코드다. 추상화는 그중 중요한 것만 남기고 나머지를 버리는 일이고,
버리고 남긴 것에 이름을 붙이면 층이 하나 생긴다. 그 층의 높이가 추상화 레벨이다.

높다는 것은 세부를 덜 다룬다는 뜻이다. `next_step()` 은 "답을 받아 다음 질문이나 순위를 돌려준다"만
말하고, 금리를 어떻게 더하는지는 말하지 않는다. 낮다는 것은 세부를 직접 다룬다는 뜻이다.
공시가 준 `"BNK내맘대로\n적금"` 에서 개행을 떼는 함수는 문자 하나 단위로 일한다.
둘 다 필요하지만, 한 자리에 섞이면 읽는 사람이 걸려 넘어진다.

이 프로젝트에서 레벨의 기준은 두 가지다.
**첫째, 무엇을 다루는가** — 흐름을 다루면 높고, 도메인 값을 다루면 중간이고,
문자열·dict·HTTP 응답 같은 자료구조를 다루면 낮다.
**둘째, 어느 디렉터리에 있는가** — 디렉터리가 곧 층이라서, 경로만 보고도 그 파일이 다룰 것과
다루면 안 될 것이 정해진다. 이 문서의 나머지는 그 두 번째 기준을 자세히 적은 것이다.

---

## 2. 기본 단위 — 레벨을 재는 단위는 파일이다

함수 하나가 아니라 **파일 하나가 레벨의 단위다.**

파일은 `import` 로 열고 위에서 아래로 읽는 하나의 글이다. 글 하나의 주제가 하나이듯
파일 하나의 높이도 하나다. 흐름을 조립하는 함수들 사이에 문자열을 자르는 함수가 끼어 있으면,
읽는 사람은 파일 이름을 보고 기대한 높이와 다른 것을 만난다.

판정은 한 문장이다. **파일 이름을 듣고 떠올린 것과 다른 층의 함수가 그 안에 있는가.**

그래서 이 프로젝트의 파일들은 이름과 경로가 곧 레벨 선언이다.
`app/service/question/question_flow.py` 는 질문 흐름 조립만 있고,
`app/model/vo/product_rate.py` 는 금리라는 값과 그 값의 계산만 있다.

---

## 3. 전체 그림 — 계층별 레벨

최상위는 세 영역이다. 이름 하나로 역할이 드러난다.

| 영역 | 파일 수 | 무엇인가 |
|---|---|---|
| `web` | 4 | 바깥에서 들어오는 문 — HTTP |
| `app` | 89 | 업무가 사는 곳 |
| `infra` | 4 | 업무가 쓰는 재료를 보관할지 |

`app` 은 `infra` 를 모른다. 바꿔 끼우는 일은 `bootstrap/container/` 한 곳에서만 일어난다.

디렉터리를 높은 것부터 낮은 것 순으로 놓으면 이렇다.

| 레벨 | 디렉터리 | 무엇을 하는 층인가 | 여기 있으면 안 되는 것 |
|---|---|---|---|
| 1 (가장 높다) | `web/controllers` | 요청 받기, Service 호출, 응답 반환 | 판정, 계산, dict 조작 |
| 2 | `app/service` | 흐름 조립, 트랜잭션 경계, 로그 | 도메인 판정 규칙, 쿼리문, 인프라 구현 |
| 3 | `infra` | `app/source` 약속의 캐시 구현 | 업무 판단, 서비스·DAO 참조 |
| 3 | `app/dto` | HTTP 경계의 요청·응답 모양 | 판정, DB 접근 |
| 4 | `app/model/database` | 테이블 정의, 저장된 값에 대한 판단 | 흐름 조립, 외부 호출 |
| 4 | `app/model/vo` | 도메인 값과 그 값의 계산·판정 | 상위 계층 참조, 저장 |
| 5 | `app/dao` | 쿼리 | 업무 규칙, 트랜잭션 커밋 |
| 6 (가장 낮다) | `app/external` | 외부 접속, 원본 응답 변환 | 우리 도메인 판정 |

네 곳은 이 순서 밖에 있다. 층이 아니라 **모든 층이 함께 쓰는 어휘**이기 때문이다.

| 디렉터리 | 무엇인가 | 여기 있으면 안 되는 것 |
|---|---|---|
| `app/enums` | 코드가 아는 값의 목록 | 판정 흐름, 외부 의존 |
| `app/constants` | 상수와 LLM 프롬프트 원문 | 계산, 분기 |
| `app/exception` | 계층을 건너 전달되는 도메인 예외 | 메시지 조립 외의 로직 |
| `app/source` | 판정 재료 공급 약속 (Protocol) — 서비스와 캐시가 함께 본다 | 구현, 업무 판단 |

부트스트랩(`bootstrap/`)은 층이 아니라 **조립 도면**이다. 어느 객체를 어느 객체에 꽂을지만 적혀 있고,
업무 판단은 하나도 없다.

### 계층 사이의 변환 지점

| 경계 | 무엇이 무엇으로 | 누가 한다 |
|---|---|---|
| HTTP → 내부 | 문자열 답변 → `AnswerVO` | `AnswerRequestDTO.to_answers()` |
| 공시 → 내부 | `disclosure.SavingProduct` → `Product` | `SavingProduct.to_product()` |
| LLM → 내부 | JSON 문자열 → `ExtractedConditionsVO` | `ConditionLlmParser.parse()` |
| 내부 → HTTP | VO·Entity → `~ResponseDTO` | 각 응답 DTO 의 `from_*` |

---

## 4. 상세 — 디렉터리별 파일과 레벨

내용이 있는 파일만 적는다. 빈 `__init__.py` 는 뺐다.
파일 수는 `app` 96개, `web` 4개, `bootstrap` 11개다(빈 `__init__.py` 제외).

### 4.1 `web/` — 레벨 1

| 파일 | 설명 |
|---|---|
| `controllers/api/v1/catalog.py` | 상품 목록·비교·상세 3개 엔드포인트 |
| `controllers/api/v1/product.py` | 공시 수신 결과 조회와 상품 갱신 엔드포인트 |
| `controllers/api/v1/question.py` | 다음 질문 또는 확정 순위를 돌려주는 엔드포인트 |
| `exception_handler.py` | 도메인 예외를 HTTP 상태코드로 옮긴다 |

세 컨트롤러 파일 안에는 함수 6개가 있고 전부 "서비스 호출 후 DTO 반환" 한 가지 모양이다.

### 4.2 `app/service/` — 레벨 2

| 파일 | 줄 수 | 설명 |
|---|---|---|
| `bank/bank.py` | 35 | 은행 조회·저장. 트랜잭션 경계를 소유한다 |
| `question/question.py` | 43 | 질문 조회와 시드 질문 보충 |
| `question/question_flow.py` | 284 | 조회 → 가입조건 → 우대금리 → 정렬 → 다음 질문/결과 조립 |
| `question/rate_candidates.py` | 20 | 금리 수집 중간 상태. DTO 를 담아 VO 가 될 수 없다 |
| `saving/bonus_structure.py` | 163 | 전체 상품의 필수·우대조건 추출 배치 |
| `saving/disclosure_sync.py` | 74 | 금감원 공시를 받아 DB 에 적재 |
| `saving/product.py` | 137 | 상품 조회·저장. 트랜잭션 경계를 소유한다 |
| `saving/product_catalog.py` | 68 | 사용자용 조회·비교 흐름 조립과 요청별 로그 |
| `saving/product_refresh.py` | 75 | 공시 수집부터 조건 구조화까지 한 번에 도는 갱신 |
| `saving/raw_product.py` | 21 | 공시 수신 결과를 그대로 돌려준다 |

**서비스는 캐시 구현을 모른다.** 판정 재료는 `app/source/` 의 공급 계약으로만 받는다.

### 4.2-a `app/source/` — 판정 재료 공급 약속

서비스와 저장 수단 사이의 경계다. 부르는 쪽은 캐시인지 직접 조회인지 모른 채 `get()` 과 `clear()` 만 쓴다.

**이 폴더에는 약속만 있다.** 세 파일 모두 VO 하나씩만 import 하고 구현을 모른다 —
그래서 서비스가 이것을 봐도 인프라에 묶이지 않는다.

| 파일 | 줄 수 | 설명 |
|---|---|---|
| `saving_products_source.py` | 17 | 상품 공급 약속 (Protocol) |
| `banks_source.py` | 11 | 은행 공급 약속 |
| `questions_source.py` | 11 | 질문 공급 약속 |

### 4.2-b `infra/` — 그 약속의 구현

업무 판단이 없고 **"보관할 것인가"만** 다룬다. 캐시를 쓸지는 `CACHE_ENABLED` 가 정하고,
바꿔 끼우는 일은 `bootstrap/container/infra.py` 한 곳에서만 일어난다.

| 파일 | 줄 수 | 설명 |
|---|---|---|
| `cache/timed_cache.py` | 42 | 세 캐시가 공유하는 TTL 보관함 |
| `cache/saving_products.py` | 38 | 상품 공급자를 감싸 TTL 동안 보관 |
| `cache/banks.py` | 38 | 은행 〃 |
| `cache/questions.py` | 38 | 질문 〃 |

캐시를 끄면 `app/service/` 의 은행·상품·질문 서비스가 그대로 공급자가 된다 —
서비스가 `get()`·`clear()` 를 갖춰 약속을 직접 만족하므로 사이에 끼는 어댑터가 없다.

`infra` 는 `app/source` 의 약속만 본다. 세션·DAO·서비스 구현을 모르며,
참조 방향은 `scripts/check_layers.py` 가 검사한다 (`python -m scripts.check_layers`).

`infra` 를 import 하는 곳은 **인프라 자신과 컨테이너뿐이다**(실측).
서비스·DTO·컨트롤러는 이 이름을 모른다.

### 4.3 `app/dto/` — 레벨 3

| 파일 | 설명 |
|---|---|
| `request/answer.py` | 동적 질문 키를 받아 `AnswerVO` 목록으로 바꾼다 |
| `response/next_step.py` | 턴 하나의 응답. status 로 질문/결과 두 형태로 갈린다 |
| `response/question.py` | 사용자에게 보여줄 질문 하나 |
| `response/ranking.py` | 확정 순위와 우대조건 판정 근거 |
| `response/product_catalog.py` | 상품 목록과 금리 옵션 응답 |
| `response/product_comparison.py` | 상품별 가입 가능 여부·만기 예상액 응답 |
| `response/product_refresh.py` | 갱신 배치 한 번의 결과 건수 |
| `response/raw_product.py` | 공시가 준 상품 한 건 (어드민 확인용) |
| `response/raw_products.py` | 공시 수신 결과 전체 (어드민 확인용) |
| `response/raw_rate_option.py` | 공시가 준 금리 옵션 한 건 (어드민 확인용) |

### 4.4 `app/model/database/` — 레벨 4 (Entity)

| 파일 | 설명 |
|---|---|
| `base.py` | 모든 테이블의 감사 컬럼 4개와 `record_change()` |
| `utc_datetime.py` | SQLite 에 UTC 시각을 저장하고 복원하는 컬럼 타입 |
| `bank.py` | 은행. 반복되는 은행명과 표기 흔들림을 한 곳에 모은다 |
| `product.py` | 적금 상품 하나. 조건 사용 가능 여부를 스스로 판단한다 |
| `rate_option.py` | 기간·적립방식별 금리 |
| `product_bonus.py` | 구 저장 형식과의 호환을 위한 단일 우대조건 |
| `product_condition.py` | 추출된 조건의 저장 상태와 원문 해시 |
| `product_condition_attempt.py` | LLM 원문을 검증 결과와 분리해 남기는 시도 기록 |
| `question.py` | 물을 질문 하나. 배포 없이 바꾸려고 DB 에 둔다 |

### 4.5 `app/model/vo/` — 레벨 4 (VO)

VO 는 24개이고 **파일 하나에 클래스 하나**다. 이 규칙은
`test/model/test_vo_dependencies.py:41` 테스트가 잠그고 있다.
같은 파일의 다른 두 테스트가 상위 계층 참조와 VO 간 순환 참조도 함께 막는다.

| 파일 | 설명 |
|---|---|
| `saving_products_vo.py` | 상품 묶음과 제공 기간 계산 |
| `banks_vo.py` | 은행 묶음과 코드→이름 조회 |
| `questions_vo.py` | 질문 묶음과 코드→제목 조회 |
| `answer_vo.py` | 답 하나. 건너뛴 답인지를 status 로 구분한다 |
| `answers_vo.py` | 지금까지 받은 답 전체 |
| `answered_amount_vo.py` | 숫자로 답한 금액의 공통 검증 — 금액 VO 들의 기반 |
| `monthly_deposit_vo.py` | 매달 넣겠다고 답한 금액. 한도 초과를 판단한다 |
| `goal_amount_vo.py` | 만기까지 모으고 싶다고 답한 금액과 달성 여부 |
| `monthly_limit_vo.py` | 월 납입 한도. 한도 없음도 상태로 표현한다 |
| `condition_context_vo.py` | 판정에 필요한 상품 쪽 문맥(은행·기간·한도) |
| `condition_answer_vo.py` | 조건 필드 하나가 요구하는 답과 그 해석 |
| `condition_predicate_vo.py` | 낱개 조건 하나. 검증과 판정을 스스로 한다 |
| `condition_group_vo.py` | 조건 묶음. all/any 로 하위 결과를 합친다 |
| `condition_bonus_vo.py` | 우대조건 하나 — 이름·가산금리·조건 |
| `condition_evidence_vo.py` | 조건의 근거가 된 공시 원문 필드와 문장 |
| `unresolved_condition_vo.py` | 근거가 모순되어 관리자 확인이 필요한 항목 |
| `other_condition_vo.py` | 판정 필드로 표현할 수 없어 체크리스트로만 두는 값 |
| `extracted_conditions_vo.py` | 한 상품에서 추출한 조건 전체와 그 검증 |
| `manual_conditions_vo.py` | 사람이 직접 작성한 조건. 원문 해시로 대상 상품을 확인한다 |
| `product_condition_source_vo.py` | 조건 추출의 입력이 된 공시 원문 묶음과 그 해시 |
| `checked_bonus_vo.py` | 우대조건 하나의 판정 결과와 미응답 목록 |
| `product_rate.py` | 이 상품 이 기간의 금리가 지금 얼마이고 왜 그런가 |
| `product_ranking_vo.py` | 금리 순 정렬과 다음에 물을 것 고르기 |
| `product_eligibility_vo.py` | 이 상품에 가입할 수 있는가와 그 이유 |
| `product_option_comparison_vo.py` | 옵션 하나의 비교 결과 — 금리·가입 가능·만기액 |
| `maturity_estimate_vo.py` | 매월 같은 금액을 넣을 때의 세전 예상 만기액 |

### 4.6 `app/dao/` — 레벨 5

| 파일 | 설명 |
|---|---|
| `bank.py` | 은행 조회·병합 |
| `product.py` | 상품과 거기 딸린 금리 옵션·우대조건 쿼리 |
| `question.py` | 질문 조회·병합 |

세 파일 모두 `AsyncSession` 을 인자로 받는 정적 메서드만 있고, 커밋은 하지 않는다.

### 4.7 `app/external/` — 레벨 6

| 파일 | 줄 수 | 설명 |
|---|---|---|
| `disclosure/__init__.py` | 33 | 공시 낱말과 우리 낱말의 매핑 방향을 밝히는 모듈 독스트링 |
| `disclosure/api.py` | 102 | 공시 HTTP 호출과 페이지 넘기기 |
| `disclosure/code.py` | 57 | 공시 코드값을 우리 enum 으로 옮긴다 |
| `disclosure/model.py` | 282 | 공시 응답 모델과 우리 모델로의 변환 |
| `disclosure/exception.py` | 19 | 공시 호출 실패 예외 |
| `llm/__init__.py` | 7 | OpenAI 호환 규격이라는 사실을 밝히는 모듈 독스트링 |
| `llm/api.py` | 46 | LLM 에 지시와 내용을 보내고 JSON 을 받는다 |
| `llm/model.py` | 35 | 요청·응답 메시지 모양 |
| `llm/condition_response.py` | 260 | LLM JSON 의 타입 표기와 미정의 필드 정리 |
| `llm/condition_parser.py` | 44 | 프롬프트 조립 → 호출 → VO 검증까지의 한 흐름 |
| `llm/exception.py` | 87 | LLM 실패와 검증 실패를 배치 경계까지 전달 |

### 4.8 어휘 디렉터리

| 파일 | 설명 |
|---|---|
| `app/enums/answer_kind.py` | 답을 어떤 형식으로 받는가 |
| `app/enums/answer_value.py` | 예/아니요 값과 답의 상태(미응답·건너뜀·오류) |
| `app/enums/judge_kind.py` | 받은 답을 어떤 판정에 쓰는가 |
| `app/enums/next_step.py` | 턴 응답의 두 갈래(질문·완료) |
| `app/enums/product.py` | 월 납입 한도의 유무 |
| `app/enums/product_comparison.py` | 가입 가능·만기 추정·목표 달성 상태 |
| `app/enums/product_condition.py` | 조건 필드·연산자·상태 등 조건 어휘 전부 |
| `app/enums/saving.py` | 우대 판정 결과, 적립·이자 방식, 가입 제한 |
| `app/constants/product_condition.py` | 조건 중첩 깊이·개수 등 검증 상한값 |
| `app/constants/product_condition_prompt.py` | 조건 구조화 LLM 프롬프트 원문 |
| `app/constants/product_homepage_prompt.py` | 상품 홈페이지 수집 작업 지시문 |
| `app/constants/question_text.py` | 질문 선택지 문구와 고정 답변 키 |
| `app/constants/seed_question.py` | 공시와 무관하게 늘 쓰는 시드 질문 12개 |
| `app/exception/condition.py` | 조건 검증 실패를 알리는 사용자 안내용 예외 |
| `app/exception/product.py` | 요청한 상품 id 가 없을 때의 예외 |
| `app/exception/question.py` | 비교할 상품 조건이 없을 때의 예외 |

`seed_question.py` 만 예외적으로 `app/model/database/question.py` 의 `Question` 을 참조한다.
질문 객체를 직접 만들어야 시드가 성립하기 때문이고, 방향은 여전히 아래를 향한다.

### 4.9 `bootstrap/` — 조립 도면

| 파일 | 설명 |
|---|---|
| `config_base.py` | 환경변수에서 읽는 앱 설정 |
| `context.py` | logger 와 app_config 를 컨테이너에 공급하는 실행 문맥 |
| `container/application.py` | 하위 컨테이너 5개를 묶는 최상위 컨테이너 |
| `container/component.py` | DB 엔진과 세션 메이커 |
| `container/dao.py` | DAO 3개 등록 |
| `container/store.py` | 저장소를 읽고 쓰는 서비스 3개 — 트랜잭션 경계를 소유한다 |
| `container/infra.py` | 공급자 3개를 CACHE_ENABLED 로 캐시·직접조회 중에서 고른다 |
| `container/service.py` | 외부 클라이언트 2개, LLM 파서, 업무 서비스 6개의 연결 |
| `initializer/__init__.py` | 초기화 객체 공개 |
| `initializer/develop_env.py` | 개발·배치 실행 때 테이블 생성 |
| `initializer/audit_columns.py` | 기존 테이블에 감사 컬럼을 더하는 이관 |

---

## 5. 파일 안의 함수들은 같은 레벨이어야 한다

3절의 계층 표가 파일이 놓일 자리를 정한다면, 이 규칙은 그 파일 **안**을 정한다.

> 한 파일 안의 함수들은 모두 같은 높이여야 한다.

어긋난 모습은 대개 이렇게 나타난다. 흐름을 조립하는 함수 옆에 문자열을 자르는 함수가 있고,
그 옆에 dict 를 뒤지는 함수가 있다. 층 셋이 한 파일에 있는 것이다.

이 프로젝트는 두 가지 방식으로 그것을 지킨다.

**첫째, 낮은 일을 값에게 넘긴다.** 새 유틸 파일을 만드는 대신, 그 값을 가진 객체에게 일을 준다.
금리 계산은 `ProductRate` 가, 만기액 계산은 `MaturityEstimateVO` 가, 한도 적용은
`MonthlyLimitVO` 가 갖는다. `QuestionFlowService` 는 그것들을 부르기만 한다.

**둘째, 파일 하나에 주제 하나를 둔다.** VO 24개가 파일 24개에 하나씩 들어 있고,
그 사실을 테스트가 잠그고 있다. 클래스를 더 넣으려면 테스트를 고쳐야 하므로,
"여기 하나만 더" 가 일어나지 않는다.

그래서 클래스와 모듈 최상위 함수가 한 파일에 함께 있는 곳은 전체에서 3곳뿐이고, 셋 다 정상이다.

| 파일 | 함께 있는 것 | 왜 정상인가 |
|---|---|---|
| `app/dto/response/ranking.py` | `checklist()` | 같은 파일 DTO 로의 변환이라 같은 높이다 |
| `app/external/disclosure/model.py` | `hash_of()`, `_single_line()` | 파일 전체가 외부 경계다 (6절) |
| `app/external/llm/condition_response.py` | 함수 14개 | 전부 JSON 경계 정리다 (6절) |

`question_flow.py` 는 272줄에 메서드 11개로 이 저장소에서 가장 큰 파일이지만 규칙 안에 있다.
공개 메서드는 `next_step()` 하나이고, 나머지 12개는 전부 그 하나의 흐름을 위해 존재한다.
읽는 사람은 `next_step()` 만 읽고 나가거나, 궁금한 단계 하나만 열어 보면 된다.

---

## 6. 예외로 인정되는 경계 파일 — `app/external/**`

외부에서 오는 것은 우리 타입이 아니다. HTTP 응답은 dict 이고, LLM 응답은 JSON 문자열이다.
누군가는 그것을 만져야 하고, 그 일을 하는 파일은 **파일 전체가 가장 낮은 층**이다.
그러므로 그 안에서 dict 키를 뒤지고 문자열을 자르는 것은 레벨이 어긋난 것이 아니다.

대신 두 조건을 지킨다.

**첫째, 모듈 독스트링이 그 사실을 밝힌다.**
`disclosure/__init__.py` 는 공시 낱말(`Company`, `SavingProduct`)을 그대로 쓴다는 것과
우리 낱말로 바꾸는 일이 어느 메서드에서 일어나는지를 화살표로 적어 둔다.
`llm/__init__.py` 는 OpenAI 호환 규격이라 요청·응답 모양이 그쪽을 따른다고 적어 둔다.
`disclosure/model.py` 는 낱말 매핑 방향을 `__init__.py` 에서 보라고 가리킨다.

**둘째, dict 가 파일 밖으로 나가지 않는다.**
`condition_response.py` 에는 dict 를 다루는 함수가 14개 있지만 밖으로 공개되는 것은
`normalize_condition_response(str) -> str` 하나뿐이다. 문자열로 들어가 문자열로 나오고,
그것을 받은 `condition_parser.py` 가 곧바로 `ExtractedConditionsVO` 로 검증한다.
공시 쪽도 같다. `SavingProduct` 는 `.to_product()` 로 `Product` 를 내보내고,
바깥은 공시 필드 이름을 모른다.

이 두 조건이 지켜지면, 외부 규격이 바뀌었을 때 고칠 곳이 그 파일 하나로 묶인다.

---

## 7. 참조 방향

레벨이 있으면 방향이 생긴다. **높은 층은 낮은 층을 알고, 낮은 층은 높은 층을 모른다.**

```
web/controllers  →  app/service  →  app/dao  →  (DB)
                         ↓              ↓
                    app/dto       app/model/database
                         ↘             ↓
                          app/model/vo
                                ↓
                      app/enums · app/constants
```

`app/service` 는 `app/external` 도 직접 부른다. 외부 접속은 가장 낮은 층이므로 방향은 아래다.

도메인 코어(`app/model/**`)는 아무도 위를 보지 않는다. VO 는 Service·DAO·DTO·web·bootstrap 을
import 하지 않고, VO 끼리도 순환하지 않는다.

**현재 위반은 0건이다.** `app`·`web` 전체 파일의 import 를 계층 규칙에 대조해 확인했다.

---

## 8. 근거 — 실측

낮은 층의 일이 위로 새어 나왔는지 보려면, 문자열·dict 를 직접 만지는 함수가
어느 디렉터리에 있는지 세면 된다.

| 디렉터리 | 그런 함수 수 | 평가 |
|---|---|---|
| `app/external/**` | 14 | 정상 — 여기가 그 일을 하는 층이다 |
| `app/model/vo/**` | 9 | 정상 — 도메인 값 자체가 문자열인 경우다 |
| `app/model/database/**` | 4 | 정상 — 저장 값의 검증과 변환이다 |
| `app/service/**` | 1 | 9절에서 따로 본다 |
| `app/dao/**` | 0 | — |
| `app/dto/**` | 0 | — |

낮은 일이 아래에 몰려 있고 위로 갈수록 사라진다. 컨트롤러에는 한 건도 없다.

기타 수치는 아래와 같다.

| 항목 | 값 |
|---|---|
| `app`·`web`·`bootstrap` 파이썬 파일 | 117 |
| `app`·`web` 의 빈 `__init__.py` 제외 파일 | 100 |
| `app/model/vo` 의 VO 클래스 | 25 (파일당 1개) |
| 참조 방향 위반 | 0 |
| 클래스와 모듈 함수가 공존하는 파일 | 3 (전부 정상) |
| 가장 큰 파일 | `question_flow.py` 272줄, 메서드 11개 |

---

## 9. 판정이 애매한 곳

문자열을 만지면 낮은 층이라는 것이 8절의 기준이었다. 그런데 문자열을 만지지만
**그 일 자체가 도메인 판정**이라 그 층이 맞다고 본 곳이 셋 있다.

### `app/model/database/base.py` 의 `record_change()`

`actor.strip()` 과 `len(actor) > 128` 로 입력을 막는다. 문자열 조작이다.
그러나 이것은 "수정 주체는 누구여야 하는가" 라는 저장 규칙이고, 컬럼 정의가 `String(128)` 인 것과
같은 사실을 코드 쪽에서 한 번 더 지키는 것이다. 규칙과 컬럼이 같은 파일에 있어야 함께 바뀐다.
Service 로 올리면 이 검사를 빠뜨린 저장 경로가 생긴다.

### `app/model/vo/maturity_estimate_vo.py` 의 `has_special_payment_terms()`

상품명과 비고를 이어 붙여 공백을 지우고 `"매일"`, `"26주"`, `"초입금일"` 같은 낱말이 있는지 본다.
겉모습은 문자열 검색이지만, 실제로 하는 일은 **"이 상품은 매월 같은 금액 납입 가정으로
만기액을 계산해도 되는가"** 라는 판정이다. 계산 가정이 성립하는지를 아는 것은 계산하는 쪽이고,
그래서 계산을 가진 VO 가 그 판정도 갖는다.

다만 근거가 공시 원문 문구라는 점은 약한 자리다. 파일에도 그 사실이
`ponytail:` 주석으로 남아 있다 — 납입 일정이 구조화되면 그 값으로 대체한다.

### `app/service/question/question_flow.py` 의 `_unavailable_error()`

8절에서 Service 에 하나 있다고 센 함수다. 제외된 상품들의 사유를 모아
`" ".join(sorted(...))` 로 이어 붙여 예외 메시지를 만든다.
문자열 조작은 그 한 줄뿐이고, 함수의 주제는 "비교할 상품이 없다는 것을 운영 로그와
사용자 메시지 양쪽에 알린다"는 흐름이다. Service 가 예외를 만들어 던지는 것은 제 일이므로 둔다.
