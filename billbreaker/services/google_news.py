"""
Google News RSS links (news.google.com/rss/articles/<id>) no longer redirect to
the publisher. The article page decodes the id with a batchexecute call, so a
plain redirect-following request lands back on Google News. We make the same call.
"""

import json
import logging
import re
from urllib.parse import quote, urlparse

import httpx

log = logging.getLogger(__name__)

ARTICLE_PATH = re.compile(r"/(?:rss/)?articles/([^/?#]+)")
BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

_cache: dict[str, str] = {}


def google_news_id(link: str) -> str | None:
    try:
        u = urlparse(link)
    except ValueError:
        return None
    if not (u.hostname or "").endswith("news.google.com"):
        return None
    m = ARTICLE_PATH.search(u.path)
    return m.group(1) if m else None


async def _signature(client: httpx.AsyncClient, article_id: str) -> tuple[str, str] | None:
    res = await client.get(
        f"https://news.google.com/rss/articles/{article_id}", headers={"User-Agent": UA}
    )
    if res.status_code != 200:
        return None
    sg = re.search(r'data-n-a-sg="([^"]+)"', res.text)
    ts = re.search(r'data-n-a-ts="([^"]+)"', res.text)
    return (sg.group(1), ts.group(1)) if sg and ts else None


def _request_body(article_id: str, ts: str, sg: str) -> str:
    inner = json.dumps(
        [
            "garturlreq",
            [
                ["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1]
                + [None] * 5
                + [0, 1],
                "X",
                "X",
                1,
                [1, 1, 1],
                1,
                1,
                None,
                0,
                0,
                None,
                0,
            ],
            article_id,
            int(ts),
            sg,
        ],
        separators=(",", ":"),
    )
    outer = json.dumps([[["Fbv4je", inner, None, "generic"]]], separators=(",", ":"))
    return "f.req=" + quote(outer, safe="")


def parse_batch_reply(text: str) -> str | None:
    """The reply is ")]}'\\n\\n<len>\\n[[...]]"; the URL sits in a JSON string in the first row."""
    start = text.find("[[")
    if start < 0:
        return None
    row = text[start:].split("\n", 1)[0]
    try:
        payload = json.loads(row)[0][2]
        url = json.loads(payload)[1]
    except (ValueError, IndexError, TypeError, KeyError):
        return None
    return url if isinstance(url, str) and re.match(r"^https?://", url) else None


async def _decode(client: httpx.AsyncClient, article_id: str) -> str | None:
    sig = await _signature(client, article_id)
    if not sig:
        return None
    sg, ts = sig
    res = await client.post(
        BATCH_URL,
        content=_request_body(article_id, ts, sg),
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": UA,
        },
    )
    if res.status_code != 200:
        return None
    return parse_batch_reply(res.text)


async def decode_google_news_link(link: str, client: httpx.AsyncClient | None = None) -> str | None:
    article_id = google_news_id(link)
    if not article_id:
        return None
    if article_id in _cache:
        return _cache[article_id]
    url = None
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=10) as own:
                url = await _decode(own, article_id)
        else:
            url = await _decode(client, article_id)
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("google news decode failed: %s", exc)
    # Only successes are cached, so a transient failure is retried on the next refresh.
    if url:
        _cache[article_id] = url
    return url


def ap_search_url(title: str) -> str:
    """AP search for the headline: the fallback when Google will not decode an id."""
    return "https://apnews.com/search?q=" + quote(title, safe="")
