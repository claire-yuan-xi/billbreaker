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
PLAIN = re.compile(r"\b(\d{1,3})\s*Stat\.?\s*(\d{1,5})\b")
MIN_CHARS = 400


def statute_cite(wikitext: str) -> tuple[int, int] | None:
    """(volume, page) of the law in the Statutes at Large, from an infobox."""
    line = CITE_LINE.search(wikitext)
    if not line:
        return None
    m = USSTAT.search(line.group(1)) or PLAIN.search(line.group(1))
    return (int(m.group(1)), int(m.group(2))) if m else None


def statute_url(volume: int, page: int) -> str:
    return f"https://www.govinfo.gov/link/statute/{volume}/{page}"


async def remember(bill_no: str, volume: int, page: int) -> None:
    await db.execute(
        "INSERT INTO statute_links (bill_no, url) VALUES (?, ?) ON CONFLICT(bill_no) DO UPDATE SET url = excluded.url",
        (bill_no, statute_url(volume, page)),
    )


async def fetch_statute_text(client: httpx.AsyncClient, bill_no: str, timeout: float):
    """The law's printed text, when a search saved where it is."""
    row = await db.query_one("SELECT url FROM statute_links WHERE bill_no = ?", (bill_no,))
    if not row:
        return None
    # Old printed volumes are scanned PDFs, so they need longer than a web page.
    doc = await read_document(client, row["url"], max(timeout, 15))
    return (doc.text, row["url"]) if len(doc.text) >= MIN_CHARS else None
