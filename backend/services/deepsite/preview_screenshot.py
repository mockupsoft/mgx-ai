# -*- coding: utf-8 -*-
"""
DeepSite canlı önizleme URL'si için PNG ekran görüntüsü (Playwright).

Kurulum (geliştirici / CI):
  pip install playwright
  playwright install chromium

Docker: backend imajına Chromium bağımlılıkları + `playwright install chromium` eklenmeli;
aksi halde endpoint 503 döner.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def capture_url_png(
    url: str,
    *,
    viewport_width: int = 1280,
    viewport_height: int = 720,
    full_page: bool = False,
    wait_ms: int = 2000,
    navigation_timeout_ms: int = 45_000,
) -> bytes:
    """
    Verilen HTTP(S) URL'yi headless Chromium ile açıp PNG baytı döndürür.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise RuntimeError(
            "playwright paketi yüklü değil. Kurulum: pip install playwright && playwright install chromium"
        ) from e

    if not url.startswith(("http://", "https://")):
        raise ValueError("Geçersiz URL şeması")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
            ],
        )
        try:
            page = await browser.new_page(
                viewport={"width": viewport_width, "height": viewport_height}
            )
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=navigation_timeout_ms,
            )
            if wait_ms > 0:
                await asyncio.sleep(wait_ms / 1000.0)
            png: bytes = await page.screenshot(full_page=full_page, type="png")
            return png
        finally:
            await browser.close()


def describe_playwright_setup() -> str:
    """Hata yanıtlarında kullanılacak kısa talimat."""
    return (
        "Playwright Chromium bulunamadı veya başlatılamadı. "
        "Yerel: `pip install playwright` ve `playwright install chromium`. "
        "Docker: backend imajına Playwright sistem bağımlılıkları ve tarayıcı kurulumu ekleyin."
    )
