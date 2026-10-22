"""
Free web search with no API key: Bing's RSS results, then DuckDuckGo's HTML page.
Used to find a page about a bill when no official source answered.
"""

import html
import re
from urllib.parse import parse_qs, quote, urlparse

import httpx

from .text import extract_tag

UA = "Mozilla/5.0 (compatible; BillBreaker/1.0)"
DDG_LINK = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', re.I)


def parse_bing(xml: str) -> list[dict]:
    results = []
    for raw in xml.split("<item>")[1:]:
        block = raw.split("</item>")[0]
        url = html.unescape(extract_tag("link", block))
        title = html.unescape(extract_tag("title", block))
        if url.startswith("http"):
            results.append({"url": url, "title": title})
    return results


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


async def search(client: httpx.AsyncClient, query: str, timeout: float = 6) -> tuple[str, list[dict]]:
    """Returns which engine answered and its results, best first."""
    engines = (
        ("bing", f"https://www.bing.com/search?format=rss&count=20&q={quote(query, safe='')}", parse_bing),
        ("duckduckgo", f"https://html.duckduckgo.com/html/?q={quote(query, safe='')}", parse_ddg),
    )
    for name, url, parse in engines:
        try:
            res = await client.get(url, timeout=timeout, headers={"User-Agent": UA, "Accept-Language": "en-US"})
        except httpx.HTTPError:
            continue
        found = parse(res.text) if res.status_code == 200 else []
        if found:
            return name, found
    return "", []
