import asyncio

from billbreaker.api import explain as explain_api
from billbreaker.services import analysis_cache, bill_views, prewarm
from billbreaker.services.ai_client import AIError
from billbreaker.services.bill_sources import FetchResult

QUICK = {"tldr": "hi", "who_it_affects": [], "key_numbers": []}
BILL_TEXT = "SEC. 1. SHORT TITLE. " + "words " * 100


def fake_sources(monkeypatch, calls):
    async def fetch(state, bill_no):
        calls.append(f"{state} {bill_no}")
        return FetchResult(text=BILL_TEXT, source_url="https://example.gov", source="govinfo")

    async def explain(bill, identifier):
        return f"Title of {identifier}", [{"event": "quick_take", "data": QUICK}]

    monkeypatch.setattr(prewarm, "fetch_bill_text", fetch)
    monkeypatch.setattr(prewarm, "breakdown", explain)


def test_opening_a_bill_counts_a_view(client):
    asyncio.run(analysis_cache.save("US", "HR 1", analysis_cache.hash_text("x" * 300), "Cached", None, [{"event": "quick_take", "data": QUICK}]))
    for _ in range(2):
        client.post("/api/explain-bill", json={"state": "US", "billNo": "HR1", "text": "x" * 300})
    assert asyncio.run(bill_views.popular(5)) == [{"state": "US", "bill_no": "HR 1", "views": 2}]


def test_refreshes_the_most_opened_bills_first(monkeypatch):
    calls = []
    fake_sources(monkeypatch, calls)
    for bill, views in (("HR 2", 1), ("HR 1", 3)):
        for _ in range(views):
            asyncio.run(bill_views.count("US", bill))
    results = asyncio.run(prewarm.run())
    assert calls == ["US HR 1", "US HR 2"]
    assert [r["status"] for r in results] == ["refreshed", "refreshed"]
    fresh = asyncio.run(analysis_cache.load_fresh("US", "HR 1", analysis_cache.hash_text(BILL_TEXT)))
    assert fresh["title"] == "Title of US HR 1"


def test_skips_bills_whose_breakdown_is_still_fresh(monkeypatch):
    calls = []
    fake_sources(monkeypatch, calls)
    asyncio.run(bill_views.count("US", "HR 1"))
    asyncio.run(analysis_cache.save("US", "HR 1", "h", "Fresh", None, []))
    assert asyncio.run(prewarm.run()) == []
    assert calls == []


def test_stops_when_the_ai_limit_is_reached(monkeypatch):
    calls = []
    fake_sources(monkeypatch, calls)

    async def limited(bill, identifier):
        raise AIError("RATE_LIMIT")

    monkeypatch.setattr(prewarm, "breakdown", limited)
    for bill in ("HR 1", "HR 1", "HR 2"):
        asyncio.run(bill_views.count("US", bill))
    assert asyncio.run(prewarm.run()) == [{"bill": "US HR 1", "status": "RATE_LIMIT"}]


def test_cron_route_runs_once_per_day(client, monkeypatch):
    fake_sources(monkeypatch, [])
    first = client.get("/api/cron/prewarm").json()
    second = client.get("/api/cron/prewarm").json()
    assert first == {"ok": True, "results": []}
    assert second["skipped"] == "ran recently"


def test_cron_route_checks_the_secret_when_set(client, set_setting):
    set_setting("cron_secret", "s3cret")
    assert client.get("/api/cron/prewarm").status_code == 401
    ok = client.get("/api/cron/prewarm", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200
