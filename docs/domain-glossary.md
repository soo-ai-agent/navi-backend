# 도메인 어휘 사전

이 저장소에서 같은 것을 두 이름으로 부르지 않기 위한 기준이다.
새 이름을 지을 때 여기 있는 낱말을 쓰고, 여기 없는 낱말이 필요하면 이 문서에 먼저 추가한다.

낱말이 흔들리면 읽는 사람이 "이 둘이 같은 것인가"를 매번 추측하게 된다.

---

## 1. saving 과 product — 가장 헷갈리는 한 쌍

둘 다 "적금 상품"을 가리키는 것처럼 보이지만 **쓰는 자리가 다르다.**

| 낱말 | 뜻 | 쓰는 자리 |
|---|---|---|
| `saving` | 금감원 공시가 부르는 이름 | 외부 경계(`app/external/disclosure/`)와 그 원문을 담는 타입 |
| `product` | 우리가 저장하고 비교하는 상품 | 그 밖의 모든 곳 |

경계를 넘는 순간 이름이 바뀐다. `SavingProduct.to_product()` 가 그 자리다.

```
금감원 공시            우리 도메인
SavingProduct     →    SavingProduct
SavingProducts    →    SavingProducts
```

**판정: `app/external/disclosure/` 밖에서 새로 만드는 이름에 `saving` 을 넣지 않는다.**

### 공시 필드명은 바꾸지 않는다

경계 안쪽(`app/external/disclosure/model.py`)에서는 공시가 준 키를 **그대로** 필드명으로 쓴다.
`spcl_cnd` 를 `special_condition` 으로 풀어 쓰지 않는다 — 공시 문서와 대조할 때마다 번역해야 하기 때문이다.

실측: `SavingProduct` 13개, `SavingProductOption` 7개 필드가 전부 공시 키와 같다. 지어낸 이름은 없다.

| 공시 키 | 뜻 |
|---|---|
| `fin_co_no` · `fin_prdt_cd` | 회사 번호 · 상품 코드 (둘을 합쳐 `product_id`) |
| `spcl_cnd` | 우대조건 원문 |
| `mtrt_int` | 만기 후 금리 안내 |
| `intr_rate` · `intr_rate2` | 기본금리 · 최고금리 |
| `save_trm` | 저축 기간(개월) |
| `join_deny` | 가입 제한 코드 |

이름을 우리 것으로 바꾸는 자리는 `to_product()`·`to_rate_option()` 한 곳뿐이다.

**예외 — 같은 이름이 두 가지를 가리킬 때.** 공시는 상품 목록과 회사 목록을 **둘 다 `baseList`** 라고 부른다.
그대로 두면 타입마다 같은 이름이 다른 것을 담아 읽는 사람이 구분할 수 없다. 이때만 Pydantic `alias` 로 바꾼다.

```python
products: tuple[SavingProduct, ...] = Field(alias="baseList")     # 적금 페이지
companies: tuple[Company, ...] = Field(alias="baseList")          # 회사 페이지
```

`alias` 라서 받는 키는 공시 그대로이고, 코드에서 부르는 이름만 우리 것이다.

### 예외 둘

`saving_term_months`(저축 기간)와 `available_saving_terms()` 는 내부에서도 `saving` 을 쓴다.
"적금 기간"이 한 낱말이라 `product_term` 으로 바꾸면 오히려 뜻이 흐려진다.

`AllSavings` 는 이 규칙과 어긋난 이름이다 — 아래 5절 참고.

---

## 2. 상품을 가리키는 세 가지 모양

같은 상품이라도 어느 단계에 있느냐에 따라 타입과 이름이 다르다.

| 이름 | 무엇인가 | 어디 있나 |
|---|---|---|
| `SavingProduct` | 공시 API 가 준 원문 | `app/external/disclosure/model.py` |
| `Product` | DB 에 저장된 상품 | `app/model/database/product.py` |
| `ProductRate` | 한 상품·한 기간의 금리 계산 결과 | `app/model/vo/product_rate.py` |

`raw` 가 붙으면 "가공하지 않은 공시 원문"이라는 뜻이다 (`RawProductsResponseDTO`, `RawProductService`).

---

## 3. 조건 어휘

적금의 "조건"은 두 종류이고 결코 섞이지 않는다.

| 낱말 | 뜻 | 못 지키면 |
|---|---|---|
| `eligibility` (가입조건) | 가입할 수 있는가 | 상품이 후보에서 빠진다 |
| `bonus` (우대조건) | 금리를 더 받는가 | 기본금리만 적용된다 |

둘을 아우를 때만 `condition` 을 쓴다. `ExtractedConditionsVO` 가 그 예로, 안에 `eligibility` 와 `bonuses` 를 함께 담는다.

| 낱말 | 뜻 |
|---|---|
| `extracted` | AI 가 원문에서 뽑아낸 구조화 결과 |
| `checked` | 사용자 답으로 판정을 마친 상태 (`CheckedBonusVO`) |
| `unanswered` | 판정에 필요한데 아직 답이 없는 조건 |
| `predicate` | 조건 하나의 비교식 (필드·연산자·값) |
| `group` | 여러 predicate 를 AND/OR 로 묶은 것 |

---

## 4. 금리 어휘

| 낱말 | 뜻 |
|---|---|
| `base_rate` | 기본금리 |
| `bonus_rate` | 우대금리 (조건 충족 시 가산) |
| `rate` | 실제 적용될 금리 (기본 + 확정된 우대) |
| `possible_rate` | 미확정 우대까지 다 받았을 때의 금리 |
| `rate_option` | 한 상품이 제공하는 기간별 금리 묶음 |

`rate` 는 **판정이 끝난 값**이고 `possible_rate` 는 **아직 답하지 않은 조건을 다 충족했다고 가정한 값**이다.
순위를 매길 때 둘이 갈리면 그 조건을 사용자에게 묻는다.

---

## 5. 어그리게이트 경계 — 도메인마다 제 타입을 갖는다

판정에 쓰는 재료는 도메인별로 나뉘어 있고, **필요한 것만 받는다.**

| VO | 담는 것 | 할 줄 아는 것 |
|---|---|---|
| `SavingProductsVO` | 상품 묶음 | `available_saving_terms()` |
| `BanksVO` | 은행 묶음 | `of(code)` · `name(code)` |
| `QuestionsVO` | 질문 묶음 | `title(code, default)` |

캐시도 같은 선을 따라 나뉘고, 각자 자기 도메인 서비스 하나만 주입받는다.

| 공급자(Protocol) | 캐시 구현 | 직접 조회 |
|---|---|---|
| `SavingProductsSource` | `SavingProductsCache` | `ProductService` |
| `BanksSource` | `BanksCache` | `BankService` |
| `QuestionsSource` | `QuestionsCache` | `QuestionService` |

약속은 `app/source/`, 캐시는 `infra/cache/` 에 산다. 직접 조회는 서비스가 `get()`·`clear()` 를
갖춰 약속을 그대로 만족하므로 별도 클래스가 없다.
부르는 서비스는 약속만 알고 캐시 구현을 모른다.

**어느 쪽을 쓸지는 `CACHE_ENABLED` 설정이 정한다.** 컨테이너의 `providers.Selector` 가 바꿔 끼우고,
부르는 쪽은 어느 구현인지 모른다 — `get()` 과 `clear()` 만 안다.

```
CACHE_ENABLED=false  →  요청마다 DB 를 다시 읽는다 (갱신이 즉시 보인다)
CACHE_ENABLED=true   →  TTL 10분 캐시 (기본)
```

TTL 보관 로직은 `TimedCache` 하나에 모여 있다 — 세 캐시가 그것을 쓴다.

**갱신 배치는 세 공급자를 모두 비운다.** 공시 적재가 은행도 새로 넣기 때문에
상품만 비우면 새 은행이 최대 TTL 동안 안 보인다.

**부르는 쪽은 쓰는 것만 받는다.** `ProductComparisonsResponseDTO.from_savings()` 는 상품만,
`QuestionResponseDTO.for_monthly_deposit()` 은 질문만 받는다. 인자 목록이 곧 의존 선언이다.

---

## 6. 이름과 내용이 어긋난 것

고치면 파급이 큰데 이득이 작아 그대로 둔 것이다. 새 코드에서 따라 하지 않는다.

### `app/service/saving/` 디렉터리

안에 있는 서비스는 전부 `product` 를 다룬다(`ProductService`, `ProductCatalogService`, `ProductRefreshService`).
디렉터리 이름만 `saving` 이다. 도메인 폴더 이름이라 경로 변경의 파급이 커 유지한다.

---

## 6. 새 이름을 지을 때

1. 이 문서에 그 낱말이 있는가 — 있으면 그대로 쓴다.
2. 같은 것을 이미 다른 이름으로 부르고 있지 않은가 — 그렇다면 기존 이름을 쓴다.
3. 외부 경계의 낱말을 안쪽으로 들여오고 있지 않은가 — 경계에서 바꾼다.
4. 새 낱말이 필요하면 이 문서에 먼저 추가하고 쓴다.
