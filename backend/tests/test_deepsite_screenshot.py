# -*- coding: utf-8 -*-
"""DeepSite preview_screenshot — tam paket importu olmadan yükleme (hafif test)."""

import asyncio
import importlib.util
from pathlib import Path

import pytest


def _load_preview_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "services" / "deepsite" / "preview_screenshot.py"
    spec = importlib.util.spec_from_file_location("deepsite_preview_screenshot", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_describe_playwright_setup_nonempty():
    mod = _load_preview_module()
    assert "playwright" in mod.describe_playwright_setup().lower()


def test_capture_url_png_invalid_scheme():
    mod = _load_preview_module()

    async def _run():
        await mod.capture_url_png("ftp://example.com")

    with pytest.raises(ValueError):
        asyncio.run(_run())
