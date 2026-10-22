"""
Finds a bill on the open web when no official source answered: searches for it,
reads the best few pages that name the bill, and returns their text.
"""

import asyncio
import ipaddress
import re
from urllib.parse import urlparse

import httpx

from ..states import STATE_NAMES
from .text import strip_html
from .web_search import search

UA = "Mozilla/5.0 (compatible; BillBreaker/1.0)"
MAX_PAGES = 4
KEEP_PAGES = 2
PAGE_CHARS = 40_000
MIN_CHARS = 400
MAX_BYTES = 3_000_000

TRACKERS = (
    "legiscan.com",
    "billtrack50.com",
    "pluralpolicy.com",
    "openstates.org",
    "fastdemocracy.com",
    "trackbill.com",
    "govtrack.us",
    "congress.gov",
    "govinfo.gov",
)
SKIP = ("youtube.com", "facebook.com", "x.com", "twitter.com", "instagram.com", "tiktok.com", "reddit.com", "linkedin.com")
OFFICIAL_WORDS = re.compile(r"legis|senate|house|assembly|capitol|statehouse", re.I)
LONG_NAMES = {"HB": "House Bill", "SB": "Senate Bill", "AB": "Assembly Bill", "HR": "H.R.", "S": "S."}


def bill_pattern(bill_no: str) -> re.Pattern | None:
    """Matches HB 12, H.B. 12, HB12 and House Bill 12, but not HB 120."""
    m = re.match(r"([A-Z]+)\s*0*(\d+)([A-Z]?)$", bill_no.upper().replace(".", "").strip())
    if not m:
        return None
    prefix, number = m.group(1), m.group(2)
    short = r"\.?\s?".join(re.escape(c) for c in prefix) + r"\.?\s?"
    names = [short]
    if prefix in LONG_NAMES:
        names.append(re.escape(LONG_NAMES[prefix]).replace(r"\ ", r"\s+") + r"\s*")
    return re.compile(rf"\b(?:{'|'.join(names)})(?:No\.?\s*)?0*{number}(?!\d)", re.I)


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _public(url: str) -> bool:
    host = _host(url)
    if not url.startswith(("https://", "http://")) or not host or host == "localhost":
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        return True


def _rank(url: str) -> int:
    host = _host(url)
    if any(host == s or host.endswith("." + s) for s in SKIP):
        return -1
    if host.endswith((".gov", ".us")) or OFFICIAL_WORDS.search(host):
        return 3
    if any(host == t or host.endswith("." + t) for t in TRACKERS):
        return 2
    return 1


def query_for(state: str, bill_no: str) -> str:
    if state == "US":
        return f"{bill_no} bill Congress"
    return f"{STATE_NAMES.get(state, state)} legislature {bill_no} bill"


async def _page(client: httpx.AsyncClient, url: str, timeout: float) -> str:
    try:
        res = await client.get(url, timeout=timeout, headers={"User-Agent": UA, "Accept": "text/html,text/plain"})
    except httpx.HTTPError:
        return ""
    kind = res.headers.get("content-type", "")
    readable = "html" in kind or "text/plain" in kind
    if res.status_code != 200 or not readable or len(res.content) > MAX_BYTES:
        return ""
    return strip_html(res.text)


async def fetch_web_text(client: httpx.AsyncClient, state: str, bill_no: str, timeout: float = 6):
    """Returns (text, first page url) from pages that name the bill, or None."""
    pattern = bill_pattern(bill_no)
    if not pattern:
        return None
    _engine, results = await search(client, query_for(state, bill_no), timeout)
    candidates = [r["url"] for r in results if _public(r["url"]) and _rank(r["url"]) > 0]
    candidates = sorted(dict.fromkeys(candidates), key=_rank, reverse=True)[:MAX_PAGES]
    pages = await asyncio.gather(*(_page(client, url, timeout) for url in candidates))
    kept = [(url, text) for url, text in zip(candidates, pages) if len(text) >= MIN_CHARS and pattern.search(text)]
    if not kept:
        return None
    kept = kept[:KEEP_PAGES]
    text = "\n\n".join(f"Source: {url}\n{body[:PAGE_CHARS]}" for url, body in kept)
    return text, kept[0][0]
