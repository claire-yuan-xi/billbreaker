"""
Finds a bill on the open web when no official source answered: searches for it,
reads the best few pages that name the bill, and follows a legislature page one
step to the bill's own text when it links to it.
"""

import asyncio
import ipaddress
import re
from datetime import date
from urllib.parse import urljoin, urlparse

import httpx

from ..states import STATE_NAMES
from ..validation import split_congress
from .documents import Document, read_document
from .web_search import search

MAX_PAGES = 4
KEEP_PAGES = 2
PAGE_CHARS = 40_000
MIN_CHARS = 400

TRACKERS = (
    "billtrack50.com",
    "pluralpolicy.com",
    "openstates.org",
    "fastdemocracy.com",
    "trackbill.com",
    "govtrack.us",
    "congress.gov",
    "govinfo.gov",
)
# Social sites never hold bill text; LegiScan answers this host with a bot check.
SKIP = (
    "youtube.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "instagram.com",
    "tiktok.com",
    "reddit.com",
    "linkedin.com",
    "legiscan.com",
)
OFFICIAL_WORDS = re.compile(r"legis|senate|house|assembly|capitol|statehouse", re.I)
HREF = re.compile(r'href="([^"#]+)"', re.I)
TEXT_LINK = re.compile(r"\.(?:htm|html|txt|pdf)$|billtext|/text", re.I)
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
    """Legislature sites first, then bill trackers, then other government sites."""
    host = _host(url)
    if any(host == s or host.endswith("." + s) for s in SKIP):
        return -1
    if OFFICIAL_WORDS.search(host):
        return 4
    if any(host == t or host.endswith("." + t) for t in TRACKERS):
        return 3
    if host.endswith((".gov", ".us")):
        return 2
    return 1


def query_for(state: str, bill_no: str) -> str:
    """Names this year so the current session's bill outranks a famous old one."""
    if state == "US":
        return f"{bill_no} bill Congress"
    return f"{STATE_NAMES.get(state, state)} legislature {bill_no} {date.today().year}"


def text_links(doc: Document) -> list[str]:
    """Links on a legislature page, to the same site, that look like the bill's text."""
    host = _host(doc.url)
    links = dict.fromkeys(urljoin(doc.url, h) for h in HREF.findall(doc.html))
    return [u for u in links if _host(u) == host and _public(u) and TEXT_LINK.search(urlparse(u).path or "")]


async def _follow(client: httpx.AsyncClient, doc: Document, pattern: re.Pattern, timeout: float) -> Document:
    """The bill's own text when a legislature page links to it, else the page itself."""
    if _rank(doc.url) != 4 or not doc.html:
        return doc
    for link in text_links(doc)[:2]:
        linked = await read_document(client, link, timeout)
        if len(linked.text) > len(doc.text) // 2 and len(linked.text) >= MIN_CHARS and pattern.search(linked.text):
            return linked
    return doc


async def fetch_web_text(client: httpx.AsyncClient, state: str, bill_no: str, timeout: float = 6):
    """Returns (text, first page url) from pages that name the bill, or None."""
    pattern = bill_pattern(split_congress(bill_no)[0])
    if not pattern:
        return None
    results = await search(client, query_for(state, bill_no), timeout)
    # Only legislature sites and bill trackers: other pages that mention a bill
    # number are often about an older bill with the same number.
    candidates = [r["url"] for r in results if _public(r["url"]) and _rank(r["url"]) >= 3]
    candidates = sorted(dict.fromkeys(candidates), key=_rank, reverse=True)[:MAX_PAGES]
    docs = await asyncio.gather(*(read_document(client, url, timeout) for url in candidates))
    kept = [d for d in docs if len(d.text) >= MIN_CHARS and pattern.search(d.text)][:KEEP_PAGES]
    if not kept:
        return None
    kept[0] = await _follow(client, kept[0], pattern, timeout)
    text = "\n\n".join(f"Source: {d.url}\n{d.text[:PAGE_CHARS]}" for d in kept)
    return text, kept[0].url
