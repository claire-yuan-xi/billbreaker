import asyncio
from urllib.parse import quote

import httpx

from billbreaker.services import ap_news
from billbreaker.services.bing_news import fetch_bing_ap_items, unwrap_bing_link


def click(target: str) -> str:
    return f"http://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;url={quote(target, safe='')}&amp;mkt=en-us"


def feed(items):
    body = "".join(
        f"<item><title>{t}</title><link>{click(u)}</link><pubDate>{d}</pubDate></item>" for t, u, d in items
    )
    return f'<?xml version="1.0"?><rss><channel>{body}</channel></rss>'


XML = feed(
    [
        ("Older &amp; quieter", "https://apnews.com/article/old", "Mon, 12 Oct 2026 10:00:00 GMT"),
        ("Newest", "https://apnews.com/article/new", "Sat, 17 Oct 2026 08:00:00 GMT"),
    ]
)


def run_with(handler, coro_fn):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await coro_fn(client)

    return asyncio.run(go())


def test_unwraps_the_ap_article():
    assert unwrap_bing_link(click("https://apnews.com/article/abc").replace("&amp;", "&")) == "https://apnews.com/article/abc"


def test_drops_links_off_apnews():
    assert unwrap_bing_link(click("https://example.com/story").replace("&amp;", "&")) is None
    assert unwrap_bing_link("not a url") is None


def test_merges_dedupes_and_sorts_newest_first():
    items = run_with(lambda r: httpx.Response(200, text=XML), fetch_bing_ap_items)
    assert [i["link"] for i in items] == ["https://apnews.com/article/new", "https://apnews.com/article/old"]
    assert items[1]["title"] == "Older & quieter"


def test_returns_nothing_when_every_query_fails():
    assert run_with(lambda r: httpx.Response(503, text="nope"), fetch_bing_ap_items) == []


def test_headlines_fall_back_to_bing_when_google_refuses(monkeypatch):
    def handler(request):
        if "news.google.com" in str(request.url):
            return httpx.Response(503)
        return httpx.Response(200, text=XML)

    real = httpx.AsyncClient
    monkeypatch.setattr(ap_news.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler)))
    result = asyncio.run(ap_news.legislation_news())
    assert result["error"] is None
    assert result["items"][0]["link"] == "https://apnews.com/article/new"
