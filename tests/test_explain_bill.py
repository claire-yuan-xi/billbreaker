import asyncio
import json

from billbreaker.api import explain as explain_api
from billbreaker.services import analysis_cache
from billbreaker.services.ai_client import AIError
from billbreaker.services.bill_sources import FetchResult

TEXT = "x" * 300
QUICK = {"tldr": "hi", "who_it_affects": [], "key_numbers": []}


def post(client, **body):
    return client.post("/api/explain-bill", json={"state": "US", "billNo": "HR1", "text": TEXT, **body})


def test_rejects_an_invalid_state(client):
    res = post(client, state="ZZ")
    assert res.status_code == 400
    assert "state" in res.json()["error"].lower()


def test_rejects_a_malformed_bill_number(client):
    assert post(client, billNo="<script>").status_code == 400


def test_rejects_oversize_text(client):
    assert post(client, text="a" * 200_001).status_code == 413


def test_serves_the_cache_as_sse_without_auth(client):
    asyncio.run(analysis_cache.save("US", "HR1", analysis_cache.hash_text(TEXT), "Cached", None, [{"event": "quick_take", "data": QUICK}]))
    res = post(client)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert "event: quick_take" in res.text and "event: done" in res.text


def test_serves_the_cache_as_json_with_rendered_html(client):
    asyncio.run(analysis_cache.save("US", "HR1", analysis_cache.hash_text(TEXT), "Cached bill", "https://example", [{"event": "quick_take", "data": QUICK}]))
    body = post(client, mode="json").json()
    assert body["title"] == "Cached bill"
    assert body["cached"] is True
    assert body["quick_take"] == QUICK
    assert "hi" in body["html"]["quick_take"]


def test_rate_limit_returns_429_with_retry_after(client):
    for _ in range(15):
        post(client, text="y" * 300 + "z", mode="json")
    res = post(client, text="y" * 300 + "z", mode="json")
    assert res.status_code == 429
    assert 0 < int(res.headers["retry-after"]) <= 60


def test_rate_limit_fails_closed_when_the_store_errors(client, monkeypatch):
    async def broken(*args):
        raise RuntimeError("db down")

    monkeypatch.setattr("billbreaker.services.rate_limit._bump", broken)
    res = post(client, mode="json")
    assert res.status_code == 429
    assert res.headers["retry-after"] == "60"


def test_falls_back_to_the_last_analysis_when_ai_fails(client):
    other = "w" * 300
    asyncio.run(analysis_cache.save("US", "HR1", analysis_cache.hash_text(other), "Old title", "https://old", [{"event": "quick_take", "data": QUICK}]))
    body = post(client, mode="json").json()
    assert body["cached"] is True
    assert body["title"] == "Old title"
    assert body["cached_reason"] == "ai_unavailable"
    assert body["cached_at"]


def test_streams_an_error_with_json_fallback_when_ai_fails(client, monkeypatch):
    async def failing(bill, identifier):
        raise AIError("AI_GATEWAY_ERROR")

    monkeypatch.setattr(explain_api, "breakdown", failing)
    res = post(client)
    payload = json.loads(res.text.strip().splitlines()[-1].removeprefix("data: "))
    assert payload["fallback"] == "json"


def test_a_missing_key_is_named_and_not_retried(client):
    res = post(client)
    payload = json.loads(res.text.strip().splitlines()[-1].removeprefix("data: "))
    assert "GEMINI_API_KEY" in payload["message"]
    assert "fallback" not in payload


def test_streams_a_fresh_breakdown(client, monkeypatch):
    async def fake(bill, identifier):
        return "Plain title", [{"event": "quick_take", "data": QUICK}]

    monkeypatch.setattr(explain_api, "breakdown", fake)
    res = post(client, text="v" * 300)
    assert "Plain title" in res.text and "event: quick_take" in res.text and "event: done" in res.text


def test_fetches_the_text_when_none_is_pasted(client, monkeypatch):
    async def fake_fetch(state, bill_no):
        return FetchResult(TEXT, "https://www.congress.gov/x", "congress.gov", ["congress.gov"])

    monkeypatch.setattr(explain_api, "fetch_bill_text", fake_fetch)
    asyncio.run(analysis_cache.save("US", "HR1", analysis_cache.hash_text(TEXT), "Fetched", None, [{"event": "quick_take", "data": QUICK}]))
    body = post(client, text="", mode="json").json()
    assert body["title"] == "Fetched"
    assert body["source"] == "congress.gov"
