---
name: saving-homepage-finder
description: >-
  적금 상품의 은행 공식 안내 페이지 주소(homepage_url)를 찾아 채우는 Agent Skill.
  금융감독원 공시는 상품 URL을 주지 않으므로 에이전트가 직접 검색해 채운다.
  homepage_url 이 빈 상품을 채우라는 요청, 상품 홈페이지 적재·검증
  (data/product-homepage.json, import_saving_homepages, crawl_saving_pages) 작업에 사용할 것.
  틀린 주소는 사용자를 엉뚱한 상품으로 보내므로, 확실하지 않으면 빈 값으로 둔다.
---

# 적금 상품 홈페이지 찾기

적금 상품의 은행 공식 안내 페이지 주소를 찾아 DB `product.homepage_url` 에 채운다.
비어 있는 상품은 화면이 은행 대표 홈페이지로 보내므로, **틀린 주소가 빈 주소보다 나쁘다.**

작업 기록은 [references/fill-log.md](references/fill-log.md) 에 남긴다.

## 실행 순서

### 1. 빈 상품 조회 (읽기 전용)

```bash
sqlite3 -readonly data/backend.db \
  "SELECT p.product_id, b.display_name, p.name FROM product p
   JOIN bank b ON p.bank_code=b.bank_code WHERE p.homepage_url='';"
```

### 2. 웹검색

"은행명 상품명" 으로 검색한다. 예: "수협은행 헤이(Hey)적금"

### 3. 공식 도메인 판별 + 상품명 일치 확인

- **은행 공식 도메인만 쓴다.** 블로그·뉴스·금리비교 사이트는 쓰지 않는다.
- 페이지를 열어 **상품명이 정확히 일치하는지** 확인한다. 같은 은행의 비슷한 이름을
  혼동하지 않는다 — "자유적립식"과 "정액적립식"은 다른 상품이다.
- 상품 상세 페이지가 가장 좋다. 없으면 그 상품이 들어 있는 목록 페이지도 쓸 수 있다.
- 로그인해야 보이는 주소, 세션이 붙은 주소(jsessionid 등)는 쓰지 않는다.
- **확실하지 않으면 빈 문자열로 둔다.**

**같은 은행의 다른 상품**: 주소에 상품코드가 들어가는 은행이 있다. 한 상품을 찾았으면
코드만 바꿔 다른 상품도 열어 보되, 실제로 그 상품이 나오는지 **확인한 뒤에** 쓴다.
확인 없이 코드만 바꾸지 않는다.
예: 중소기업은행은 `.../PNTR701000_i2.jsp?...&pdcd=0113&tmcd=121` 에서 pdcd 가 상품코드다.

### 4. data/product-homepage.json 기입

`{"product_id": "url", ...}` 형식. import 스크립트는 파일에 없는 상품과 빈 값("")을
건너뛰므로, **채울 상품만 담으면 기존 값은 건드리지 않는다.** 못 찾은 상품은 빼거나 "" 로 둔다.

### 5. 적재

```bash
/tmp/navi_venv/bin/python scripts/import_saving_homepages.py
```

적재 전후 `SELECT COUNT(*) FROM product WHERE homepage_url != ''` 로 반영 수를 확인한다.

### 6. 크롤링 검증

```bash
/tmp/navi_venv/bin/python scripts/crawl_saving_pages.py
```

주소를 실제 브라우저(Playwright)로 열어 화면 글을 `data/product-pages/<상품>-page.json` 에
저장한다. 은행 페이지는 대부분 자바스크립트로 본문을 그려서 단순 HTTP 요청으로는 빈 문서가 온다.

저장한 뒤 반드시 확인한다:

- `text` 에 그 상품 이름이 있는가. 없으면 주소가 틀렸다는 뜻이다.
- `text_length` 가 0이면 로그인 페이지이거나 앱 전용 화면이다.
- 목록 페이지를 넣었다면 그 상품이 목록 안에 실제로 있는지 본다.

### 7. 틀리면 빈 값 복구

검증에 실패한 상품은 json 에서 빈 문자열로 되돌리고 다시 적재한다. import 스크립트는
빈 값을 건너뛰므로 DB 복구는 `UPDATE product SET homepage_url='' WHERE product_id=...`
로 직접 한다 (검증 실패 상품에 한해서만).

## 크롤링 원문의 용도

저장한 원문은 공시에 없는 설명(우대조건 세부, 가입 절차, 중도해지 안내)을 사람이 보완할 때
근거로 쓴다. 공시 원문과 다르면 공시가 정본이고, 은행 페이지는 참고다.
