"""
Fallback headline source. Google News refuses some hosting networks (it answers
Cloudflare with a 503), so the AP stories come from Bing News RSS instead. Bing
returns about a dozen items per query, so a few legislation queries are merged.
"""

import asyncio
import html
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, quote, urlparse

import httpx

from .text import extract_tag

QUERIES = ["legislation", "bill congress", "lawmakers", "senate bill", "governor signs bill"]
UA = "Mozilla/5.0 BillBreaker"


def feed_url(query: str) -> str:
    q = quote(f"site:apnews.com {query}", safe="")
    return f"https://www.bing.com/news/search?q={q}&qft=sortbydate%3d%221%22&format=rss"


def unwrap_bing_link(link: str) -> str | None:
    """Bing wraps each story in an apiclick.aspx redirect; the article sits in `url`."""
    try:
        target = parse_qs(urlparse(link).query).get("url", [""])[0]
        host = (urlparse(target).hostname or "").lower()
    except ValueError:
        return None
    return target if host == "apnews.com" or host.endswith(".apnews.com") else None


def parse_bing_feed(xml: str) -> list[dict]:
    items = []
    for raw in xml.split("<item>")[1:]:
        block = raw.split("</item>")[0]
        link = unwrap_bing_link(html.unescape(extract_tag("link", block)))
        title = html.unescape(extract_tag("title", block))
        if link and title:
            items.append({"title": title, "link": link, "pubDate": extract_tag("pubDate", block), "source": "AP News"})
    return items


async def _query(client: httpx.AsyncClient, query: str) -> list[dict]:
    res = await client.get(feed_url(query), headers={"User-Agent": UA})
    return parse_bing_feed(res.text) if res.status_code == 200 else []


def _timestamp(item: dict) -> float:
    try:
        return parsedate_to_datetime(item["pubDate"]).timestamp()
    except (TypeError, ValueError):
        return 0


async def fetch_bing_ap_items(client: httpx.AsyncClient, limit: int = 40) -> list[dict]:
    batches = await asyncio.gather(*(_query(client, q) for q in QUERIES), return_exceptions=True)
    seen, items = set(), []
    for batch in batches:
        if isinstance(batch, BaseException):
            continue
        for item in batch:
            if item["link"] not in seen:
                seen.add(item["link"])
                items.append(item)
    items.sort(key=_timestamp, reverse=True)
    return items[:limit]
