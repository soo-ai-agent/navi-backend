# `question_flow.py` — 함수별 기능과 추상화 레벨

대상: `app/service/question/question_flow.py` (284줄, 클래스 `QuestionFlowService`, 메서드 11개)

판정 기준은 `gyurinet-abstraction` 이다 — 한 함수 안의 문장은 같은 높이여야 하고, 함수 이름은 본문을 대신할 수 있어야 한다.
아래 수치(줄 수·인자 수·로그 수·분기 수)는 AST 로 센 실측값이다.

---

## 1. 이 파일이 하는 일

사용자 답변을 받아 **다음에 무엇을 돌려줄지** 정한다. 셋 중 하나다.

- 아직 물어볼 것이 남았다 → 질문 하나
- 다 물었다 → 금리 순위 10개
- 비교할 상품이 하나도 없다 → 503 예외

이 파일은 흐름만 조립한다. "이 상품에 가입할 수 있는가", "우대금리가 붙는가", "무엇을 먼저 물어야 하는가" 같은 판정은
`Product`·`ConditionGroupVO`·`ProductRankingVO` 가 한다.

---

## 2. 호출 구조

위에서 아래로 읽으면 이 순서다. 들여쓰기가 호출 깊이다.

```
next_step                     ← 공개. 로그 시작·끝, 소요시간
└─ _decide                    ← 흐름의 뼈대. 6단계 분기
   ├─ _selected_terms         ← 기간 답변 해석
   ├─ _collect_candidates     ← 상품 전체 순회
   │  ├─ _options_in_terms    ← 선택 기간에 맞는 옵션만 고른다
   │  ├─ _excluded_product    ← 조건 미확정 상품을 기록으로 바꾼다
   │  ├─ _eligibility_question← 가입조건 미응답 → 질문 하나
   │  └─ _product_rate        ← 우대조건 판정 → 금리 후보 하나
   ├─ _unavailable_error      ← 503 예외 조립 + 사유 집계
   └─ _ranked_step            ← 정렬 → 우대 질문 or 결과 10개
```

공개 메서드가 위, 비공개가 호출 순서대로 아래 — 파일 배치가 이 그림과 일치한다.

---

## 3. 함수별 기능

### `next_step(answers) -> NextStepResponseDTO`

| 항목 | 값 |
|---|---|
| 줄 수 | 19 |
| 하는 일 | request_id 발급 → `_decide` 호출 → 결과·소요시간 로그 |
| 판정 | 없음 |

요청 하나의 **바깥 테두리**다. 성공이든 실패든 종료 로그를 남기고 예외는 그대로 위로 던진다.
`gyurinet-logging` 의 "시작과 끝은 짝을 이룬다" 를 이 함수 하나가 책임진다.

### `_decide(request_id, answers) -> NextStepResponseDTO`

| 항목 | 값 |
|---|---|
| 줄 수 | 30 |
| 하는 일 | 재료 조회 → 고정 질문 3개 순서대로 확인 → 상품 순회 → 결과 분기 |
| 판정 | 없음 (판정 결과로 분기만 한다) |

이 파일의 **목차**다. 다섯 개의 `if` 가 있지만 전부 "아직 물을 게 있으면 돌려준다" 한 가지 모양이라 위에서 아래로 읽힌다.

기간 → 월납입 → 목표금액 순서가 고정돼 있다. 이 순서가 바뀌면 이 함수만 고친다.

### `_selected_terms(answers, term_question, products) -> tuple[int, ...] | None`

| 항목 | 값 |
|---|---|
| 줄 수 | 16 |
| 하는 일 | 기간 답변 문자열을 개월 수 튜플로 |
| 판정 | 건너뜀이면 전체 기간, 미응답·잘못된 값이면 `None` |

`None` 은 "다시 물어야 한다"는 뜻이다. HTTP 문자열 → `int` 변환이 이 파일에서 유일하게 일어나는 자리이며 주석이 그 사유를 적고 있다.

### `_collect_candidates(request_id, answers, products, banks, selected_terms) -> RateCandidates`

| 항목 | 값 |
|---|---|
| 줄 수 | 46 (가장 길다) |
| 하는 일 | 상품 × 옵션을 돌며 제외 / 질문 / 금리 후보 셋으로 나눈다 |
| 판정 | 없음 — `product.verified_conditions()`, `eligibility.evaluate()` 가 한다 |

상품마다 세 갈래로 갈린다.

1. 조건 추출이 안 끝났다 → `_excluded_product` 로 기록
2. 가입조건 판정이 `UNKNOWN` → `_eligibility_question` 으로 질문 하나 만들고 **즉시 반환**
3. 가입 가능 → `_product_rate` 로 금리 후보

2번에서 즉시 반환하는 이유가 주석에 있다 — 답 하나가 늘면 모든 상품의 판정이 바뀌므로 여기까지 계산한 것은 버린다.

### `_options_in_terms(product, selected_terms) -> list[RateOption]`

| 항목 | 값 |
|---|---|
| 줄 수 | 6 |
| 하는 일 | 상품의 금리 옵션 중 선택 기간에 해당하는 것만 |
| 판정 | 없음 (필터) |

### `_excluded_product(product, status, selected_terms) -> ExcludedProductVO | None`

| 항목 | 값 |
|---|---|
| 줄 수 | 13 |
| 하는 일 | 조건 미확정 상품을 제외 기록으로 만든다. 선택 기간에 옵션이 없으면 기록하지 않는다 |
| 판정 | 사유 문장은 `product.condition_unavailable_reason()` 이 만든다 |

`stored_status`(DB 에 저장된 상태)와 `status`(이번 판정 상태)를 따로 담는다. 둘이 다를 수 있다 — 저장은 `EXTRACTED` 인데 검증에서 `NEEDS_REVIEW` 로 떨어지는 경우다. `product.condition` 을 직접 들여다보는 줄이 있다(§5-2).

### `_product_rate(request_id, answers, product, option, extracted, context) -> ProductRate`

| 항목 | 값 |
|---|---|
| 줄 수 | 25 |
| 하는 일 | 우대조건마다 판정·미응답 목록을 모아 `ProductRate` 하나로 |
| 판정 | `bonus.condition.evaluate()` / `.unanswered()` 가 한다 |

인자가 6개로 가장 많다. 상품·옵션·추출 결과·문맥이 전부 필요한 자리이긴 하나, 그중 셋(`option`·`extracted`·`context`)은 전부 `product` 에서 파생된 값이다 (§5 참고).

### `_eligibility_question(request_id, answers, banks, product, context, eligibility) -> QuestionResponseDTO | None`

| 항목 | 값 |
|---|---|
| 줄 수 | 16 |
| 하는 일 | 가입조건 중 아직 안 물어본 것 하나를 질문으로. 물을 게 없으면 `None` |
| 판정 | `eligibility.unanswered()` 가 한다 |

`None` 은 "판정이 `UNKNOWN` 인데 물어볼 것도 없다" — 데이터 결함이라 제외한다.

### `_unavailable_error(request_id, products, selected_terms, excluded) -> ProductConditionsUnavailableError`

| 항목 | 값 |
|---|---|
| 줄 수 | 24 |
| 하는 일 | 상태별 제외 건수를 세어 WARN 한 줄, 상품별 DEBUG, 사유를 모아 예외 메시지 |
| 판정 | 없음 (집계) |

예외를 **던지지 않고 만들어 돌려준다**. 호출부 `_decide` 가 `raise` 한다. 그래서 반환 타입이 예외 클래스다.

### `_ranked_step(request_id, banks, rates) -> NextStepResponseDTO`

| 항목 | 값 |
|---|---|
| 줄 수 | 21 |
| 하는 일 | 금리 후보를 정렬 → 우대조건 질문이 남았으면 질문, 아니면 상위 10개 |
| 판정 | `ProductRankingVO.from_rates()` / `.next_answer()` 가 한다 |

`_RESULT_SIZE = 10` 이 여기서만 쓰인다.

---

## 4. 추상화 레벨 판정

### 4.1 파일 레벨 — 한 층인가

**그렇다.** 11개 메서드 전부 "흐름 조립 + 로그" 층에 있다. `abstraction-layers.md` 가 `app/service` 에 두지 말라고 한 것 —
도메인 판정 규칙, 쿼리문, 인프라 구현 — 이 하나도 없다.

판정이 일어나는 자리를 세면 명확하다.

| 판정 | 누가 하나 | 이 파일에서 |
|---|---|---|
| 조건 추출이 끝났는가 | `Product.verified_conditions()` | 결과로 분기만 |
| 가입할 수 있는가 | `ConditionGroupVO.evaluate()` | 결과로 분기만 |
| 무엇을 안 물었나 | `ConditionGroupVO.unanswered()` | 첫 번째를 질문으로 |
| 우대금리가 붙는가 | `bonus.condition.evaluate()` | 결과를 모을 뿐 |
| 다음에 무엇을 물을까 | `ProductRankingVO.next_answer()` | 결과로 분기만 |
| 제외 사유가 무엇인가 | `Product.condition_unavailable_reason()` | 문장을 받을 뿐 |

이 파일에 `if` 는 18개 있지만 전부 **다른 객체가 내린 판정 결과**로 갈라진다. 값을 꺼내 바깥에서 계산하는 곳(`if product.status == ...`)이 없다.

### 4.2 함수 레벨 — 각 함수 안이 한 높이인가

| 함수 | 높이 | 한 높이인가 | 근거 |
|---|---|---|---|
| `next_step` | 최상 | ✅ | 호출 하나 + 로그. 본문에 업무 단어가 없다 |
| `_decide` | 상 | ✅ | 전부 팩토리 호출과 `self._*` 호출. 6단계가 같은 굵기 |
| `_selected_terms` | 중 | ✅ | 답변 → 기간 변환 한 가지. `int()` 가 유일한 저수준 조작이고 사유 주석 있음 |
| `_collect_candidates` | 중 | ⚠️ | 아래 §5-1 |
| `_options_in_terms` | 하 | ✅ | 필터 한 줄짜리 뜻 |
| `_excluded_product` | 중 | ⚠️ | 아래 §5-2 |
| `_product_rate` | 중 | ✅ | 루프 하나, 객체 조립 하나 |
| `_eligibility_question` | 중 | ✅ | 물어본다 / 안 물어본다 |
| `_unavailable_error` | 중 | ⚠️ | 아래 §5-3 |
| `_ranked_step` | 중 | ✅ | 정렬 → 질문 or 결과. 두 갈래가 같은 굵기 |

`_decide` 가 호출하는 다섯 함수(`_selected_terms`·`_collect_candidates`·`_unavailable_error`·`_ranked_step` + 팩토리)가 **같은 높이**에 있는 것이 이 파일의 핵심이다.
`_decide` 를 읽을 때 어느 줄에서도 `for` 나 dict 조작을 만나지 않는다.

`_collect_candidates` 가 호출하는 넷(`_options_in_terms`·`_excluded_product`·`_eligibility_question`·`_product_rate`)도 서로 같은 높이다 — 전부 "상품 하나 + 부가 정보 → 결과 하나".

### 4.3 이름이 본문을 대신하는가

| 이름 | 본문을 안 열고 알 수 있는 것 | 평가 |
|---|---|---|
| `next_step` | 다음 단계를 준다 | ✅ |
| `_decide` | 정한다 — 무엇을? | △ 넓다. 단 이 클래스에서 정할 것은 "다음 단계" 하나뿐이라 문맥이 채운다 |
| `_selected_terms` | 선택된 기간들 | ✅ |
| `_collect_candidates` | 후보를 모은다 | ✅ |
| `_options_in_terms` | 기간 안의 옵션들 | ✅ |
| `_excluded_product` | 제외된 상품 | ✅ |
| `_product_rate` | 상품 금리 | ✅ |
| `_eligibility_question` | 가입조건 질문 | ✅ |
| `_unavailable_error` | 이용 불가 오류 | ✅ |
| `_ranked_step` | 순위 매긴 단계 | ✅ |

bool 을 돌려주는 함수가 없어 `is_`/`has_` 규칙은 해당 없음. 줄임말 없음. 단수·복수는 반환 개수와 일치한다(`_selected_terms` → 튜플, `_product_rate` → 하나).

---

## 5. 같은 높이가 아닌 자리 — 셋

전부 **Important 이하**다. 지금 고치라는 뜻이 아니라, 이 파일을 다음에 열 때 어디부터 볼지 적어 둔다.

### 5-1. `_collect_candidates` 안의 한 줄이 한 단 낮다

```python
for option in self._options_in_terms(product, selected_terms):
    checked_any_option = True
    context: ConditionContextVO = product.condition_context(option)
    eligibility: ConditionGroupVO = extracted.eligibility          # ← 필드 접근
    eligibility_result: BonusResult = eligibility.evaluate(answers, context)
```

`extracted.eligibility` 는 값을 꺼내는 줄이고, 그 위아래는 전부 메서드 호출이다. 다음 줄에서 `eligibility.evaluate()` 와 `eligibility.unanswered()` 두 번 쓰려고 꺼낸 것이라 이유는 있다.

**그리고 같은 계산이 이 파일 밖에도 있다.**

| 위치 | 코드 |
|---|---|
| `question_flow.py:148` | `eligibility.evaluate(answers, context)` (위에서 꺼낸 값) |
| `product_eligibility_vo.py:36` | `extracted.eligibility.evaluate(answers, context)` |

같은 판정이 두 곳에 있으므로 object-design 의 전환 시점(2곳 이상)을 이미 넘겼다.
`ExtractedConditionsVO.eligibility_result(answers, context) -> BonusResult` 로 옮기면 두 호출부가 같은 이름을 부르게 되고, 이 파일에서는 필드를 꺼내는 줄이 사라진다.

단 `question_flow` 는 `unanswered()` 를 위해 `ConditionGroupVO` 자체도 필요하므로(§`_eligibility_question` 인자), 옮길 때 그 경로를 함께 봐야 한다.

### 5-2. `_excluded_product` 가 `Product` 의 내부를 두 번 본다

```python
stored_status: str = _NO_CONDITION_RECORD
if product.condition is not None:
    stored_status = product.condition.status.value
```

"저장된 상태 문자열"은 `Product` 가 답할 수 있는 질문이다. 지금은 `_NO_CONDITION_RECORD` 상수와 `None` 검사가 서비스에 있다.

`Product.stored_condition_status() -> str` 하나면 이 함수는 두 줄이 된다. 같은 함수 안에서 이미 `product.condition_unavailable_reason(status)` 를 부르고 있으니 그 옆이 제자리다.

`product.condition` 의 `None` 을 서비스가 직접 검사하는 곳은 여기만이 아니다.

| 위치 | 무엇을 묻나 |
|---|---|
| `question_flow.py:189` | 저장된 상태 문자열이 무엇인가 |
| `product.py:105` | 저장된 조건이 원문과 맞는가 |
| `bonus_structure.py:100` | 이전 조건이 있었나 |

세 곳이 각자 다른 것을 묻고 있어 한 메서드로 묶이지는 않는다. 다만 이 파일의 경우는 `_NO_CONDITION_RECORD` 라는 **표시 문자열 상수까지 서비스에 있어** 판정 조각이 새어 나온 것이 분명하다.

이것이 셋 중 가장 확실한 신호다 — 상수(`_NO_CONDITION_RECORD`)가 이 파일에서 단 한 번 쓰이며, 그 쓰임이 `Product` 의 내부 상태를 대신 설명하는 일이다.

### 5-3. `_unavailable_error` 의 집계식이 한 단 낮다

```python
status_counts: str = ", ".join(
    f"{condition_status.value}={sum(1 for product in excluded if product.status is condition_status)}"
    for condition_status in _EXCLUDED_STATUSES
)
```

한 줄에 컴프리헨션 두 개가 겹쳐 있다. 위아래 줄(`logger.warning`, `for product in excluded`)보다 눈에 띄게 촘촘하다.

`collections.Counter(product.status for product in excluded)` 로 세고 문자열은 따로 만들면 두 줄이 되고 중첩이 사라진다. 결과는 같다.

---

## 6. 요약

- 파일은 **한 층**이다. 흐름 조립만 있고 판정은 전부 도메인 객체에 있다.
- 공개 → 비공개, 호출 순서대로 배치돼 위에서 아래로 읽힌다.
- `_decide` 와 그 아래 다섯 함수, `_collect_candidates` 와 그 아래 네 함수 — 두 묶음이 각각 같은 높이다.
- 어긋난 자리는 셋이고 전부 한 줄~세 줄 규모다. 5-2 가 가장 먼저 볼 곳이다.

이 파일을 고칠 일이 생기면 §2 의 그림에서 어느 상자를 여는지 먼저 찾는다 — 고정 질문 순서면 `_decide`, 제외 기준이면 `_excluded_product`, 결과 개수면 `_ranked_step` 이다.
