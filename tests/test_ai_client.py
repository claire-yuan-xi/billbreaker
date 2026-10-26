import asyncio
import json

import httpx

from billbreaker.services import ai_client, explain

SCHEMA = {"name": "f", "description": "", "parameters": {"type": "object", "properties": {}}}


def reply(args: dict) -> httpx.Response:
    call = {"function": {"name": "f", "arguments": json.dumps(args)}}
    return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [call]}}]})


def gemini(monkeypatch, set_setting, handler):
    set_setting("gemini_api_key", "test-key")
    set_setting("gemini_model", "main-model")
    set_setting("gemini_fallback_model", "lite-model")
    seen = []

    def record(request):
        body = json.loads(request.content)
        seen.append(body.get("model") or request.url.path.split("/")[-1].split(":")[0])
        return handler(request, len(seen))

    monkeypatch.setattr(ai_client, "_transport", httpx.MockTransport(record))
    return seen


def test_out_of_quota_tries_the_fallback_model(monkeypatch, set_setting):
    seen = gemini(monkeypatch, set_setting, lambda req, n: httpx.Response(429, text="{}") if n == 1 else reply({"ok": 1}))
    assert asyncio.run(ai_client.call_ai("s", "u", SCHEMA)) == {"ok": 1}
    assert seen == ["main-model", "lite-model"]


def test_a_short_rate_limit_waits_once(monkeypatch, set_setting):
    real_sleep = asyncio.sleep
    monkeypatch.setattr(ai_client.asyncio, "sleep", lambda s: real_sleep(0))
    limited = httpx.Response(429, text='[{"error": {"details": [{"retryDelay": "3s"}]}}]')
    seen = gemini(monkeypatch, set_setting, lambda req, n: limited if n < 3 else reply({"ok": 2}))
    assert asyncio.run(ai_client.call_ai("s", "u", SCHEMA)) == {"ok": 2}
    assert seen == ["main-model", "lite-model", "lite-model"]


def test_a_refused_key_is_named(monkeypatch, set_setting):
    gemini(monkeypatch, set_setting, lambda req, n: httpx.Response(403, text="denied"))
    try:
        asyncio.run(ai_client.call_ai("s", "u", SCHEMA))
    except ai_client.AIError as exc:
        assert exc.code == "AI_FORBIDDEN"
        assert exc.detail.startswith("main-model 403")
    else:
        raise AssertionError("expected AIError")


def test_breakdown_is_one_call_with_every_section(monkeypatch, set_setting):
    data = {
        "title": "A plain title",
        "quick_take": {"tldr": "t"},
        "winners_losers": {"winners": [], "losers": []},
        "citations": {"citations": []},
        "supporters_vs_critics": {"supporters": [], "critics": []},
        "status_quo_diff": {"changes": []},
    }
    seen = gemini(monkeypatch, set_setting, lambda req, n: reply(data))
    title, sections = asyncio.run(explain.breakdown("bill text", "US HR1"))
    assert seen == ["lite-model"]
    assert title == "A plain title"
    assert [s["event"] for s in sections] == ["quick_take", "status_quo_diff", "winners_losers", "supporters_vs_critics", "citations"]


def test_research_reads_the_json_and_the_pages(monkeypatch, set_setting):
    from billbreaker.services import research

    data = {"title": "Gig workers", "quick_take": {"tldr": "t"}, "citations": {"citations": []}}
    answer = {
        "candidates": [
            {
                "content": {"parts": [{"text": "```json\n" + json.dumps(data) + "\n```"}]},
                "groundingMetadata": {"groundingChunks": [{"web": {"uri": "https://leginfo.ca.gov/x", "title": "ca.gov"}}]},
            }
        ]
    }
    seen = gemini(monkeypatch, set_setting, lambda req, n: httpx.Response(200, json=answer))
    title, sections, pages = asyncio.run(research.research_breakdown("California", "AB 5", "CA AB 5"))
    assert seen == ["main-model"]
    assert title == "Gig workers"
    assert [s["event"] for s in sections] == ["quick_take", "citations"]
    assert pages == [{"url": "https://leginfo.ca.gov/x", "title": "ca.gov"}]


def test_research_reports_a_missing_bill(monkeypatch, set_setting):
    from billbreaker.services import research

    answer = {"candidates": [{"content": {"parts": [{"text": "NOT_FOUND"}]}}]}
    gemini(monkeypatch, set_setting, lambda req, n: httpx.Response(200, json=answer))
    assert asyncio.run(research.research_breakdown("Texas", "HB 99999", "TX HB 99999")) is None


def test_the_native_call_sends_the_key_header_only(monkeypatch, set_setting):
    from billbreaker.services import research

    headers = []

    def handler(req, n):
        headers.append(req.headers)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "NOT_FOUND"}]}}]})

    gemini(monkeypatch, set_setting, handler)
    asyncio.run(research.research_breakdown("Texas", "HB 1", "TX HB 1"))
    assert headers[0]["x-goog-api-key"] == "test-key" and "authorization" not in headers[0]


def test_a_light_call_starts_with_the_fallback_model(monkeypatch, set_setting):
    seen = gemini(monkeypatch, set_setting, lambda req, n: reply({"ok": 3}))
    assert asyncio.run(ai_client.call_ai("s", "u", SCHEMA, light=True)) == {"ok": 3}
    assert seen == ["lite-model"]


def test_a_model_that_hangs_gives_the_next_one_a_turn(monkeypatch, set_setting):
    set_setting("gemini_api_key", "test-key")
    set_setting("gemini_model", "main-model")
    set_setting("gemini_fallback_model", "lite-model")
    monkeypatch.setattr(ai_client, "FIRST_TRY_S", 0.05)

    async def handler(request):
        if json.loads(request.content)["model"] == "main-model":
            await asyncio.sleep(1)
        return reply({"ok": 1})

    monkeypatch.setattr(ai_client, "_transport", httpx.MockTransport(handler))
    assert asyncio.run(ai_client.call_ai("s", "u", SCHEMA)) == {"ok": 1}
