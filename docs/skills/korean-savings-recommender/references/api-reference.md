# savingProductsSearch 실측 필드 정리

2026-09-15 실호출(`topFinGrpNo=020000`, dcls_month 202608) 응답에서 **실제로 본 것만** 적었다. 공식 문서 복사가 아니다.
검증 과정·샘플은 [verification.md](verification.md).

## 요청

```
GET https://finlife.fss.or.kr/finlifeapi/savingProductsSearch.json
```

| 파라미터 | 필수 | 실측 확인 |
|---|---|---|
| `auth` | ✅ | 32자리 키. 잘못되면 HTTP 200 + `err_cd="010"` |
| `topFinGrpNo` | ✅ | `020000`(은행)으로 확인. 다른 권역 코드는 이번에 미호출 |
| `pageNo` | ✅ | `1`. 은행 권역은 `max_page_no=1`이라 1페이지가 전부 |
| `financeCd` | 선택 | 이번에 미사용 |

User-Agent 헤더 없이도 되는지는 확인 안 함 — 스크립트는 `Mozilla/5.0` 을 붙인다.

## 응답 최상위 (`result`)

| 필드 | 실측 값/형 | 비고 |
|---|---|---|
| `err_cd` | `"000"` 정상, `"010"` 미등록 인증키 | 오류여도 HTTP 는 200 |
| `err_msg` | `"정상"` / `"미등록 인증키"` | 사용자에게 그대로 전달 |
| `prdt_div` | `"S"` | 적금 구분으로 보임 |
| `total_count` | 정상 시 int `59`, 오류 시 **문자열 `"0"`** | 형이 흔들린다 — 비교 전 int 캐스팅 |
| `max_page_no` / `now_page_no` | int `1` / `1` | 페이지 루프 종료 판정용 |
| `baseList` | 상품 59건 | |
| `optionList` | 옵션 181건 | |

## baseList 항목 (15개 필드 전부)

| 필드 | 형(실측) | 뜻 / 함정 |
|---|---|---|
| `dcls_month` | str `"202608"` | 공시 회차. 59건 전부 동일 |
| `fin_co_no` | str `"0010001"` | 금융회사 코드 — optionList 연결 키 ① |
| `fin_prdt_cd` | str `"WR0001F"` | 상품 코드 — 연결 키 ② |
| `kor_co_nm` | str | 은행명 (예: "주식회사 카카오뱅크" — 법인명 그대로) |
| `fin_prdt_nm` | str | 상품명. **개행 포함 8건** — 검색 전 공백·개행 제거 |
| `join_way` | str | "영업점,인터넷,스마트폰,전화(텔레뱅킹)" 쉼표 구분 |
| `join_deny` | str `"1"`/`"3"` | 1 제한없음(55건)·3 일부제한(4건). 2(서민전용)는 이번 회차 0건 |
| `join_member` | str | 가입대상 원문. join_deny=3 의 실제 제한이 여기 있음 |
| `spcl_cnd` | str | 우대조건 원문(개행 포함 자유 서술). 상한 표기가 첫 줄에 오는 경우 많음 |
| `mtrt_int` | str | 만기 후 이자율 서술 |
| `etc_note` | str | 유의사항. **월 한도가 max_limit 대신 여기에만 있는 상품 있음** |
| `max_limit` | int 또는 **null(15건)** | 월 최고한도. `999999999`(2건) = 제한없음. null ≠ 무제한 — etc_note 와 함께 판단 |
| `dcls_strt_day` | str | 공시 시작일 |
| `dcls_end_day` | str 또는 null | 공시 종료일 (원본 프롬프트에 없던 필드) |
| `fin_co_subm_day` | str | 제출 시각 (원본 프롬프트에 없던 필드) |

## optionList 항목 (10개 필드 전부)

| 필드 | 형(실측) | 뜻 / 함정 |
|---|---|---|
| `dcls_month` | str | base 와 동일 회차 |
| `fin_co_no` / `fin_prdt_cd` | str | baseList 연결 키 |
| `intr_rate_type` | `"S"`(169건) / `"M"`(12건) | **단리/복리 — 만기 계산식이 다르다.** M 실존(NH1934월복리적금 등) |
| `intr_rate_type_nm` | `"단리"` / `"복리"` | 표시용 한글명 |
| `rsrv_type` | `"S"`(47건) / `"F"`(134건) | 정액/자유 적립 |
| `rsrv_type_nm` | `"정액적립식"` / `"자유적립식"` | 표시용 한글명 |
| `save_trm` | **str** `"1"`,`"3"`,`"6"`,`"12"`,`"24"`,`"36"` | 개월 수인데 **문자열** — 숫자 비교 전 int 캐스팅. 1·3개월 초단기 실존 |
| `intr_rate` | float (이번 회차 null 0건) | 기본금리 %. 다른 회차엔 null 가능성 있어 방어 유지 |
| `intr_rate2` | float | 최고우대금리 %. 우대 전부 충족 가정값 |

## 연결 규칙

`(fin_co_no, fin_prdt_cd)` 쌍으로 baseList ↔ optionList 를 잇는다. 한 상품에 옵션 평균 약 3개(181/59), 기간·적립유형·금리유형 조합마다 한 줄.
