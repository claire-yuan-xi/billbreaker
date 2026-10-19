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
        seen.append(json.loads(request.content)["model"])
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
    assert seen == ["main-model"]
    assert title == "A plain title"
    assert [s["event"] for s in sections] == ["quick_take", "status_quo_diff", "winners_losers", "supporters_vs_critics", "citations"]
