"""
Free web search with no API key, from DuckDuckGo's HTML page. Used to find a
page about a bill when no official source answered. (Bing's RSS results ignore
most of the query, so it is not used.)
"""

import html
import re
from urllib.parse import parse_qs, quote_plus, urlparse

import httpx


UA = "Mozilla/5.0 (compatible; BillBreaker/1.0)"
DDG_LINK = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.I)


def _unwrap_ddg(href: str) -> str:
    """DuckDuckGo wraps each result in /l/?uddg=<target>."""
    href = html.unescape(href)
    if href.startswith("//"):
        href = "https:" + href
    target = parse_qs(urlparse(href).query).get("uddg", [""])[0]
    return target or href


def parse_ddg(page: str) -> list[dict]:
    results = []
    for href, title in DDG_LINK.findall(page):
        url = _unwrap_ddg(href)
        if url.startswith("http"):
            results.append({"url": url, "title": html.unescape(re.sub(r"<[^>]+>", "", title)).strip()})
    return results


async def search(client: httpx.AsyncClient, query: str, timeout: float = 6) -> list[dict]:
    """Results best first, or none if the search could not be read."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        res = await client.get(url, timeout=timeout, headers={"User-Agent": UA, "Accept-Language": "en-US"})
    except httpx.HTTPError:
        return []
    return parse_ddg(res.text) if res.status_code == 200 else []
