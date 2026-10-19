import asyncio
import json
from urllib.parse import unquote

import httpx

from billbreaker.services import google_news

LINK = "https://news.google.com/rss/articles/CBMiAbC123?oc=5"
AP = "https://apnews.com/article/senate-budget-vote-abc123"


def mock_client(batch_body: str, calls: list):
    def handler(request: httpx.Request):
        calls.append(request)
        if "batchexecute" in str(request.url):
            return httpx.Response(200, text=batch_body)
        return httpx.Response(200, text='<div data-n-a-sg="SIG" data-n-a-ts="1729150000"></div>')

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_decodes_the_publisher_url_and_caches_it():
    google_news._cache.clear()
    row = json.dumps([["wrb.fr", "Fbv4je", json.dumps(["garturlres", AP, 1]), None, None, None, "generic"]])
    calls = []
    client = mock_client(f")]}}'\n\n{len(row)}\n{row}\n25\n[[\"di\",42]]", calls)
    assert asyncio.run(google_news.decode_google_news_link(LINK, client)) == AP
    body = unquote(calls[1].content.decode())
    assert "CBMiAbC123" in body and "SIG" in body
    asyncio.run(google_news.decode_google_news_link(LINK, client))
    assert len(calls) == 2


def test_garbled_replies_and_other_hosts_return_none():
    google_news._cache.clear()
    client = mock_client(")]}'\n\nnonsense", [])
    assert asyncio.run(google_news.decode_google_news_link(LINK, client)) is None
    assert asyncio.run(google_news.decode_google_news_link(AP, client)) is None
