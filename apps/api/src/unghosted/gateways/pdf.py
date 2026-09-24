"""Letter PDF rendering (us-5 item 2): Playwright headless Chromium.

The one-page rule is checked after rendering by counting the produced
pages with pypdf — the browser's own layout metrics would trust the same
engine that produced the overflow, and the PDF is what gets sent anyway.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Protocol

from playwright.async_api import async_playwright
from pypdf import PdfReader

_MARGIN_MM = "20mm"


class PdfRenderError(RuntimeError):
    """Chromium failed to render the letter HTML."""


@dataclass(frozen=True)
class RenderedLetter:
    pdf_bytes: bytes
    fits_one_page: bool
    """False when the letter overflowed to a second page — the UI warns
    before attaching (us-5 item 2)."""


class PdfGateway(Protocol):
    async def render(self, html: str) -> RenderedLetter:
        """Render one letter to a single A4 PDF or raise PdfRenderError."""


class PlaywrightPdfGateway:
    """Chromium-only: page.pdf() is unimplemented on Firefox and WebKit.
    One browser launch per render — letter approval is rare and user-paced,
    so a resident browser is not worth the lifecycle complexity yet."""

    async def render(self, html: str) -> RenderedLetter:
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch()
                try:
                    page = await browser.new_page()
                    await page.set_content(html, wait_until="load")
                    pdf_bytes = await page.pdf(
                        format="A4",
                        print_background=True,
                        margin={
                            "top": _MARGIN_MM,
                            "bottom": _MARGIN_MM,
                            "left": _MARGIN_MM,
                            "right": _MARGIN_MM,
                        },
                    )
                finally:
                    await browser.close()
        except Exception as exc:
            raise PdfRenderError(f"letter pdf rendering failed: {exc}") from exc
        fits_one_page = len(PdfReader(io.BytesIO(pdf_bytes)).pages) <= 1
        return RenderedLetter(pdf_bytes=pdf_bytes, fits_one_page=fits_one_page)
