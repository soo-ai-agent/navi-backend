from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from playwright.async_api import Browser, Error as PlaywrightError, Page, async_playwright

HOMEPAGE_FILE = Path("data/product-homepage.json")
CRAWL_DIR = Path("data/product-pages")
TIMEOUT_MS = 30000
SETTLE_MS = 2500

BLANK_LINE_PATTERN = re.compile(r"\n{3,}")
SPACE_PATTERN = re.compile(r"[ \t\r\f\v]+")


def tidy(text: str) -> str:
    """화면에서 읽은 글을 정리한다. 줄마다 공백을 줄이고 빈 줄을 합친다."""
    lines: list[str] = []
    for line in text.split("\n"):
        stripped: str = SPACE_PATTERN.sub(" ", line).strip()
        if stripped:
            lines.append(stripped)
    return BLANK_LINE_PATTERN.sub("\n\n", "\n".join(lines))


async def crawl_one(browser: Browser, product_id: str, url: str) -> Mapping[str, object]:
    """상품 안내 페이지를 열어 보이는 글을 그대로 가져온다.

    은행 페이지는 대부분 자바스크립트로 본문을 그리므로 실제 브라우저로 연다.
    """
    page: Page = await browser.new_page(locale="ko-KR")
    status: int = 0
    title: str = ""
    text: str = ""
    error: str = ""
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        status = response.status if response is not None else 0
        await page.wait_for_timeout(SETTLE_MS)
        title = await page.title()
        text = tidy(await page.inner_text("body"))
    except PlaywrightError as failure:
        error = str(failure).split("\n")[0]
    finally:
        await page.close()

    return {
        "product_id": product_id,
        "url": url,
        "status": status,
        "title": title,
        "error": error,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "text_length": len(text),
    }


async def main() -> None:
    """상품 안내 페이지를 크롤링해 원문을 JSON으로 보관한다.

    저장한 원문은 공시에 없는 설명(우대조건 세부, 가입 절차 등)을 사람이 보완할 때 근거로 쓴다.
    """
    homepages: Mapping[str, str] = json.loads(HOMEPAGE_FILE.read_text(encoding="utf-8"))
    CRAWL_DIR.mkdir(parents=True, exist_ok=True)

    saved: int = 0
    empty: list[str] = []
    async with async_playwright() as driver:
        browser: Browser = await driver.chromium.launch()
        try:
            for product_id, url in homepages.items():
                if url == "":
                    continue
                page_data: Mapping[str, object] = await crawl_one(browser, product_id, url)
                if page_data["text_length"] == 0:
                    empty.append(f'{product_id}({page_data["status"]})')
                name: str = product_id.replace(":", "-")
                (CRAWL_DIR / f"{name}-page.json").write_text(
                    json.dumps(page_data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8",
                )
                saved += 1
        finally:
            await browser.close()

    print(json.dumps({"저장": saved, "본문없음": empty, "경로": str(CRAWL_DIR)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
