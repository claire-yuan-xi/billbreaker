"""Reads a web page, plain text file or PDF into plain text for the bill sources."""

import asyncio
import io
import logging
from dataclasses import dataclass

import httpx
from pypdf import PdfReader

from .text import strip_html

log = logging.getLogger(__name__)

UA = "Mozilla/5.0 (compatible; BillBreaker/1.0)"
MAX_BYTES = 8_000_000
MAX_PDF_PAGES = 80


@dataclass
class Document:
    text: str = ""
    html: str = ""
    url: str = ""
    status: int = 0


def pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages[:MAX_PDF_PAGES]).strip()
    except Exception as exc:  # noqa: BLE001 - a broken PDF just means no text
        log.warning("could not read PDF: %s", exc)
        return ""


async def read_document(client: httpx.AsyncClient, url: str, timeout: float) -> Document:
    """The document's text, and its HTML when it is a page; empty when unreadable."""
    try:
        res = await client.get(
            url, timeout=timeout, headers={"User-Agent": UA, "Accept": "text/html,text/plain,application/pdf"}
        )
    except httpx.HTTPError:
        return Document(url=url)
    final, status = str(res.url), res.status_code
    if status != 200 or len(res.content) > MAX_BYTES:
        return Document(url=final, status=status)
    kind = res.headers.get("content-type", "").lower()
    if "pdf" in kind or res.content[:5] == b"%PDF-":
        # Parsing is CPU work, so it runs off the event loop.
        return Document(text=await asyncio.to_thread(pdf_text, res.content), url=final, status=status)
    if "html" in kind or "text/plain" in kind:
        return Document(text=strip_html(res.text), html=res.text if "html" in kind else "", url=final, status=status)
    return Document(url=final, status=status)
