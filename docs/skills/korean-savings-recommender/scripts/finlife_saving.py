"""금감원 적금 공시 API(savingProductsSearch) 호출 + 만기 실수령액 계산.

스킬 korean-savings-recommender 의 코드 정본이다. SKILL.md 3·5-2절이 이 파일을 가리킨다.

사용법:
    python3 scripts/finlife_saving.py          # demo 자가 점검 + page1 실호출 요약
    from finlife_saving import load_auth_key, call_finlife_saving, fetch_all_pages, maturity
"""

from __future__ import annotations
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

BACKEND_INI = Path(__file__).resolve().parents[4] / "backend.ini"
"""스킬 위치(backend/docs/skills/korean-savings-recommender/scripts/) 기준 backend/backend.ini"""

BASE_URL = "https://finlife.fss.or.kr/finlifeapi/savingProductsSearch.json"
BANK_GROUP = "020000"


def load_auth_key() -> str:
    """FINLIFE_API_KEY 환경 변수가 있으면 그걸, 없으면 backend.ini 의 DISCLOSURE_AUTH_KEY 를 쓴다."""
    key = os.environ.get("FINLIFE_API_KEY", "")
    if key:
        return key
    if BACKEND_INI.exists():
        for line in BACKEND_INI.read_text().splitlines():
            if line.startswith("DISCLOSURE_AUTH_KEY="):
                key = line.split("=", 1)[1].strip()
    if key:
        return key
    raise SystemExit(
        "인증키 없음: FINLIFE_API_KEY 환경 변수 또는 backend.ini 의 DISCLOSURE_AUTH_KEY 를 설정할 것"
    )


def call_finlife_saving(auth: str, top_fin_grp_no: str = BANK_GROUP, page_no: int = 1,
                        finance_cd: str | None = None) -> dict | None:
    """1페이지 호출. 실패 시 사유를 출력하고 None."""
    params = {"auth": auth, "topFinGrpNo": top_fin_grp_no, "pageNo": str(page_no)}
    if finance_cd:
        params["financeCd"] = finance_cd
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except Exception as error:  # 네트워크·HTTP·타임아웃·파싱 — 사유만 알리고 멈춘다
        print("호출 실패:", type(error).__name__, error)
        return None


def fetch_all_pages(auth: str, top_fin_grp_no: str = BANK_GROUP,
                    max_pages: int = 5) -> tuple[list[dict], list[dict]]:
    """max_page_no 까지(상한 max_pages) 돌며 baseList·optionList 를 모은다."""
    bases: list[dict] = []
    options: list[dict] = []
    for page in range(1, max_pages + 1):
        data = call_finlife_saving(auth, top_fin_grp_no, page)
        if data is None:
            break
        result = data.get("result", {})
        if result.get("err_cd") != "000":
            print("API 오류:", result.get("err_cd"), result.get("err_msg"))
            break
        bases += result.get("baseList", [])
        options += result.get("optionList", [])
        if page >= result.get("max_page_no", 1):
            break
    return bases, options


def maturity(monthly: int, months: int, annual_rate: float,
             intr_rate_type: str = "S", tax: float = 0.154) -> tuple[int, float]:
    """(원금, 세후이자). intr_rate_type: S=단리, M=월복리 — optionList 에서 반드시 읽어올 것."""
    principal = monthly * months
    interest = 0.0
    # 첫 납입금은 months 개월, 마지막 납입금은 1개월 굴러간다.
    for held_months in range(1, months + 1):
        if intr_rate_type == "M":
            interest += monthly * ((1 + annual_rate / 100 / 12) ** held_months - 1)
        else:
            interest += monthly * (annual_rate / 100) * held_months / 12
    return principal, interest * (1 - tax)


def demo() -> None:
    """자가 점검: 만기 계산식 → 실호출 1페이지 요약."""
    # 단리: 월 50만 × 12개월 × 3.5% → 원금 600만, 세후이자 96,232원 (SKILL.md 5-2절 예시)
    principal, after_tax = maturity(500_000, 12, 3.5)
    assert principal == 6_000_000
    assert abs(after_tax - 96_232.5) < 1
    # 복리가 단리보다 이자가 크다
    _, compound = maturity(500_000, 12, 3.5, "M")
    assert compound > after_tax
    # 이자는 원금×금리보다 작다(납입금마다 예치 기간이 1년에 못 미침)
    assert after_tax < principal * 0.035
    print("만기 계산식 자가 점검 통과")

    auth = load_auth_key()
    data = call_finlife_saving(auth)
    if data is None:
        return
    result = data["result"]
    print("err:", result["err_cd"], result["err_msg"],
          "| total_count:", result["total_count"], "| max_page_no:", result["max_page_no"],
          "| base:", len(result["baseList"]), "| option:", len(result["optionList"]))
    top = max((o for o in result["optionList"] if o["intr_rate2"]), key=lambda o: o["intr_rate2"])
    print("최고 intr_rate2 옵션:", top["intr_rate2"], "% / save_trm", top["save_trm"],
          "개월 —", top["fin_prdt_cd"])


if __name__ == "__main__":
    demo()
