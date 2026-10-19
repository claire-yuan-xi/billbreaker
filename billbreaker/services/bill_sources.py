"""
Best-effort bill text fetcher with a fallback chain, each tier with its own timeout:
Congress.gov then GovInfo for federal bills, OpenStates for state bills.
"""

import re
import time
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import quote, urlparse

import httpx

from ..config import settings
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
GOVINFO_VERSIONS = ("ih", "is", "rh", "rs", "enr")
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
    if not chamber:
        return None
    congress = current_congress()
    for c in (congress, congress - 1):
        url = f"https://www.congress.gov/bill/{ordinal(c)}-congress/{chamber}/{parsed[1]}/text?format=txt"
        res = await _get(client, url, timeout, {"User-Agent": UA, "Accept": "text/html"})
        if not res or res.status_code != 200:
            continue
        pre = re.search(r"<pre[^>]*>([\s\S]*?)</pre>", res.text, re.I)
        text = strip_html(pre.group(1) if pre else res.text)
        if len(text) > MIN_CHARS:
            return text, url.replace("?format=txt", "")
    return None


async def fetch_govinfo_text(client: httpx.AsyncClient, bill_no: str, timeout: float = 6):
    parsed = parse_bill_no(bill_no)
    kind = parsed and GOVINFO_TYPES.get(parsed[0])
    if not kind:
        return None
    congress = current_congress()
    for c in (congress, congress - 1):
        for version in GOVINFO_VERSIONS:
            pkg = f"BILLS-{c}{kind}{parsed[1]}{version}"
            url = f"https://www.govinfo.gov/content/pkg/{pkg}/html/{pkg}.htm"
            res = await _get(client, url, timeout)
            if not res or res.status_code != 200:
                continue
            text = strip_html(res.text)
            if len(text) > MIN_CHARS:
                return text, f"https://www.govinfo.gov/app/details/{pkg}"
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
    return any(host == s.lstrip(".") or host.endswith(s) for s in OPENSTATES_HOSTS)


async def fetch_openstates_text(client: httpx.AsyncClient, state: str, bill_no: str, timeout: float = 6):
    key = settings.openstates_api_key
    parsed = parse_bill_no(bill_no)
    if not key or not parsed:
        return None
    jurisdiction = f"ocd-jurisdiction/country:us/state:{state.lower()}/government"
    search = (
        "https://v3.openstates.org/bills?jurisdiction="
        + quote(jurisdiction, safe="")
        + "&identifier="
        + quote(f"{parsed[0]} {parsed[1]}", safe="")
        + "&include=versions&per_page=1"
    )
    headers = {"User-Agent": UA, "X-API-KEY": key, "Accept": "application/json"}
    res = await _get(client, search, timeout, headers)
    if not res or res.status_code != 200:
        return None
    try:
        result = (res.json().get("results") or [None])[0]
    except ValueError:
        return None
    if not result:
        return None
    links = [link for v in result.get("versions") or [] for link in v.get("links") or []]
    link = next(
        (l for l in links if l.get("url") and re.search(r"text|html|plain", l.get("media_type") or "text/html", re.I)),
        None,
    )
    source_url = (link or {}).get("url") or ((result.get("sources") or [{}])[0].get("url") or "")
    if not source_url or not _openstates_target_ok(source_url):
        return None
    page = await _get(client, source_url, timeout, {"User-Agent": UA, "Accept": "text/html,text/plain"})
    if not page or page.status_code != 200:
        return None
    text = strip_html(page.text, keep_breaks=False)
    return (text, source_url) if len(text) >= MIN_CHARS else None


async def fetch_bill_text(state: str, bill_no: str, budget: float = 15, tier_timeout: float = 6) -> FetchResult:
    """Returns the first source with enough text, plus every source tried."""
    result = FetchResult()
    start = time.monotonic()

    def remaining() -> float:
        return max(0.0, budget - (time.monotonic() - start))

    if state == "US":
        tiers = [
            ("congress.gov", lambda c, t: fetch_congress_text(c, bill_no, t)),
            ("govinfo", lambda c, t: fetch_govinfo_text(c, bill_no, t)),
        ]
    else:
        tiers = [("openstates", lambda c, t: fetch_openstates_text(c, state, bill_no, t))]

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
