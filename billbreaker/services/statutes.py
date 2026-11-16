"""
Laws older than GovInfo's bill collection (before 1993) have no bill text there,
but GovInfo has them as printed in the Statutes at Large. A law's Wikipedia
infobox gives its citation, like 78 Stat. 241, which is saved against the bill
when a search finds it, so the text lookup can read the law from there.
"""

import re

import httpx

from .. import db
from .documents import read_document

# "| cite statutes at large = {{usstat|78|241}}" or "78 Stat. 241".
CITE_LINE = re.compile(r"statutes[ _]at[ _]large\s*=([^\n]*)", re.I)
USSTAT = re.compile(r"\{\{\s*usstat\s*\|\s*(\d{1,3})\s*\|\s*(\d{1,5})", re.I)
# {{USStatute|congress|law|volume|page|year|month|day}}
USSTATUTE = re.compile(r"\{\{\s*usstatute\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*(\d{1,3})\s*\|\s*(\d{1,5})", re.I)
PLAIN = re.compile(r"\b(\d{1,3})\s*Stat\.?\s*(\d{1,5})\b")
MIN_CHARS = 400
# Scanned volumes are large: the ADA's pages are well over the usual 8 MB limit.
MAX_BYTES = 40_000_000


def statute_cite(wikitext: str) -> tuple[int, int] | None:
    """(volume, page) of the law in the Statutes at Large, from an infobox."""
    line = CITE_LINE.search(wikitext)
    if not line:
        return None
    value = re.sub(r"&nbsp;|\u00a0", " ", line.group(1))
    m = USSTAT.search(value) or USSTATUTE.search(value) or PLAIN.search(value)
    return (int(m.group(1)), int(m.group(2))) if m else None


def statute_url(volume: int, page: int) -> str:
    return f"https://www.govinfo.gov/link/statute/{volume}/{page}"


async def remember(bill_no: str, volume: int, page: int) -> None:
    await db.execute(
        "INSERT INTO statute_links (bill_no, url) VALUES (?, ?) ON CONFLICT(bill_no) DO UPDATE SET url = excluded.url",
        (bill_no, statute_url(volume, page)),
    )


async def saved_link(bill_no: str) -> str | None:
    row = await db.query_one("SELECT url FROM statute_links WHERE bill_no = ?", (bill_no,))
    return row["url"] if row else None


async def fetch_statute_text(client: httpx.AsyncClient, bill_no: str, timeout: float):
    """The law's printed text, when a search saved where it is."""
    url = await saved_link(bill_no)
    if not url:
        return None
    # Old printed volumes are scanned PDFs, so they need longer than a web page.
    doc = await read_document(client, url, max(timeout, 20), MAX_BYTES)
    return (doc.text, url) if len(doc.text) >= MIN_CHARS else None
