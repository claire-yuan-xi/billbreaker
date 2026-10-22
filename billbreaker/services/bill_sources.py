"""
Best-effort bill text fetcher with a fallback chain, each tier with its own timeout:
GovInfo then Congress.gov for federal bills, OpenStates for state bills, then a
web search for either.
"""

import re
import time
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import quote, urlparse

import httpx

from ..config import settings
from .bill_web import OFFICIAL_WORDS, bill_pattern, fetch_web_text
from .documents import read_document
from .text import strip_html

UA = "Mozilla/5.0 (compatible; BillBreaker/1.0)"
MIN_CHARS = 400

CONGRESS_CHAMBERS = {
    "HR": "house-bill",
    "H": "house-bill",
    "HRES": "house-resolution",
    "HJRES": "house-joint-resolution",
    "HCONRES": "house-concurrent-resolution",
    "S": "senate-bill",
    "SRES": "senate-resolution",
    "SJRES": "senate-joint-resolution",
    "SCONRES": "senate-concurrent-resolution",
}
GOVINFO_TYPES = {
    "HR": "hr",
    "H": "hr",
    "HRES": "hres",
    "HJRES": "hjres",
    "HCONRES": "hconres",
    "S": "s",
    "SRES": "sres",
    "SJRES": "sjres",
    "SCONRES": "sconres",
}
OPENSTATES_HOSTS = (".gov", ".us", "legiscan.com", "openstates.org")
PRIVATE_HOST = re.compile(r"^(localhost|127\.|10\.|192\.168\.|169\.254\.|::1|fc00:|fd00:)", re.I)


@dataclass
class FetchResult:
    text: str | None = None
    source_url: str | None = None
    source: str | None = None
    tried: list[str] = field(default_factory=list)


def parse_bill_no(bill_no: str) -> tuple[str, str] | None:
    m = re.match(r"^([A-Za-z]+)[.\s-]?(\d{1,6})$", bill_no.strip())
    return (m.group(1).upper(), m.group(2)) if m else None


def current_congress(today: date | None = None) -> int:
    return ((today or date.today()).year - 1789) // 2 + 1


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


async def _get(client: httpx.AsyncClient, url: str, timeout: float, headers: dict | None = None):
    try:
        return await client.get(url, timeout=timeout, headers=headers or {"User-Agent": UA})
    except httpx.HTTPError:
        return None


async def fetch_congress_text(client: httpx.AsyncClient, bill_no: str, timeout: float = 6):
    parsed = parse_bill_no(bill_no)
    chamber = parsed and CONGRESS_CHAMBERS.get(parsed[0])
    pattern = bill_pattern(bill_no)
    if not chamber or not pattern:
        return None
    congress = current_congress()
    for c in (congress, congress - 1):
        url = f"https://www.congress.gov/bill/{ordinal(c)}-congress/{chamber}/{parsed[1]}/text?format=txt"
        res = await _get(client, url, timeout, {"User-Agent": UA, "Accept": "text/html"})
        if not res or res.status_code != 200:
            continue
        pre = re.search(r"<pre[^>]*>([\s\S]*?)</pre>", res.text, re.I)
        text = strip_html(pre.group(1) if pre else res.text)
        if len(text) > MIN_CHARS and pattern.search(text[:3000]):
            return text, url.replace("?format=txt", "")
    return None


async def fetch_govinfo_text(client: httpx.AsyncClient, bill_no: str, timeout: float = 6):
    """GovInfo's link service, which answers with the newest printed version of the bill."""
    parsed = parse_bill_no(bill_no)
    kind = parsed and GOVINFO_TYPES.get(parsed[0])
    pattern = bill_pattern(bill_no)
    if not kind or not pattern:
        return None
    congress = current_congress()
    for c in (congress, congress - 1):
        url = f"https://www.govinfo.gov/link/bills/{c}/{kind}/{parsed[1]}?link-type=html"
        res = await _get(client, url, timeout)
        if not res or res.status_code != 200:
            continue
        text = strip_html(res.text)
        # A missing bill still answers 200 with a "Page Not Found" page.
        if len(text) > MIN_CHARS and pattern.search(text[:3000]):
            pkg = re.search(r"BILLS-[0-9a-z]+", str(res.url))
            return text, f"https://www.govinfo.gov/app/details/{pkg.group(0)}" if pkg else url
    return None


def _openstates_target_ok(url: str) -> bool:
    """SSRF guard: OpenStates is third-party, so only fetch https legislative hosts."""
    try:
        u = urlparse(url)
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    if u.scheme != "https" or not host or PRIVATE_HOST.match(host):
        return False
    if OFFICIAL_WORDS.search(host):
        return True
    return any(host == s.lstrip(".") or host.endswith(s) for s in OPENSTATES_HOSTS)


def _https(url: str) -> str:
    """Open States often lists plain http links; every legislature site serves https."""
    return "https://" + url[len("http://"):] if url.startswith("http://") else url


def openstates_links(bill: dict) -> list[str]:
    """Web pages of the bill's text, newest version first, then PDFs, then the state's page.

    Versions without a date keep Open States' order, which lists the newest first.
    """
    versions = sorted(bill.get("versions") or [], key=lambda v: v.get("date") or "", reverse=True)
    links = [link for v in versions for link in v.get("links") or [] if link.get("url")]
    pages = [l["url"] for l in links if "pdf" not in (l.get("media_type") or "").lower()]
    pdfs = [l["url"] for l in links if "pdf" in (l.get("media_type") or "").lower()][:2]
    sources = [s["url"] for s in bill.get("sources") or [] if s.get("url")]
    urls = [_https(u) for u in pages + pdfs + sources]
    return [u for u in dict.fromkeys(urls) if _openstates_target_ok(u)]


def _openstates_summary(bill: dict) -> str:
    """What Open States itself knows, used when the state's text cannot be read."""
    parts = [f"{bill.get('identifier', '')}: {bill.get('title', '')}"]
    parts += [a.get("abstract", "") for a in bill.get("abstracts") or []]
    action = bill.get("latest_action_description")
    if action:
        parts.append(f"Latest action ({bill.get('latest_action_date', '')}): {action}")
    return "\n\n".join(p for p in parts if p.strip())


async def find_openstates_bill(client: httpx.AsyncClient, state: str, bill_no: str, timeout: float = 6):
    """The bill's Open States record, newest session first, and why there is none."""
    key = settings.openstates_api_key
    parsed = parse_bill_no(bill_no)
    if not key or not parsed:
        return None, "no key" if not key else "bad number"
    jurisdiction = f"ocd-jurisdiction/country:us/state:{state.lower()}/government"
    search = (
        "https://v3.openstates.org/bills?jurisdiction="
        + quote(jurisdiction, safe="")
        + "&identifier="
        + quote(f"{parsed[0]} {parsed[1]}", safe="")
        + "&include=versions&include=sources&include=abstracts&sort=latest_action_desc&per_page=1"
    )
    headers = {"User-Agent": UA, "X-API-KEY": key, "Accept": "application/json"}
    res = await _get(client, search, timeout, headers)
    if not res:
        return None, "no answer"
    if res.status_code != 200:
        return None, f"{res.status_code}: {res.text[:200]}"
    try:
        bill = (res.json().get("results") or [None])[0]
    except ValueError:
        return None, "not JSON"
    return bill, "" if bill else "no such bill"


async def fetch_openstates_text(client: httpx.AsyncClient, state: str, bill_no: str, timeout: float = 6):
    bill, _why = await find_openstates_bill(client, state, bill_no, timeout)
    if not bill:
        return None
    for url in openstates_links(bill)[:4]:
        doc = await read_document(client, url, timeout)
        if len(doc.text) >= MIN_CHARS:
            return doc.text, url
    summary = _openstates_summary(bill)
    if bill.get("abstracts") and len(summary) >= 200:
        return summary, bill.get("openstates_url") or ""
    return None


async def fetch_bill_text(state: str, bill_no: str, budget: float = 25, tier_timeout: float = 6) -> FetchResult:
    """Returns the first source with enough text, plus every source tried."""
    result = FetchResult()
    start = time.monotonic()

    def remaining() -> float:
        return max(0.0, budget - (time.monotonic() - start))

    if state == "US":
        tiers = [
            ("govinfo", lambda c, t: fetch_govinfo_text(c, bill_no, t)),
            ("congress.gov", lambda c, t: fetch_congress_text(c, bill_no, t)),
        ]
    else:
        tiers = [("openstates", lambda c, t: fetch_openstates_text(c, state, bill_no, t))]
    tiers.append(("web", lambda c, t: fetch_web_text(c, state, bill_no, t)))

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for name, run in tiers:
            result.tried.append(name)
            if remaining() <= 0:
                continue
            found = await run(client, min(tier_timeout, remaining()))
            if found:
                result.text, result.source_url = found
                result.source = name
                return result
    return result


def official_search_url(state: str, bill_no: str) -> str:
    if state == "US":
        return (
            "https://www.congress.gov/quick-search/legislation?wordsPhrases=&legislationNumbers="
            + quote(bill_no, safe="")
        )
    return f"https://legiscan.com/gaits/search?state={state}&bill_number={quote(bill_no, safe='')}"
