import asyncio

from billbreaker.services import abuse

HOOK = "https://hooks.example.com/x"


def event():
    return abuse.Event(identifier="ip:1.2.3.4", reason="limit_exceeded", endpoint="explain-bill", count=16, limit=15, window_s=60)


def test_no_webhook_means_no_alert(set_setting, monkeypatch):
    set_setting("abuse_alert_webhook_url", "")
    sent = []
    monkeypatch.setattr(abuse, "post_with_retry", lambda *a, **k: sent.append(a))
    asyncio.run(abuse.maybe_alert(event()))
    assert sent == []


def test_http_webhooks_are_refused(set_setting):
    set_setting("abuse_alert_webhook_url", "http://hooks.example.com/x")
    assert abuse.webhook_url() is None


def test_alerts_once_per_cooldown_after_the_threshold(set_setting, monkeypatch):
    set_setting("abuse_alert_webhook_url", HOOK)
    set_setting("abuse_alert_threshold", 3)
    sent = []

    async def fake_post(url, body, **kwargs):
        sent.append(body)
        return {"ok": True, "attempts": 1}

    monkeypatch.setattr(abuse, "post_with_retry", fake_post)
    for _ in range(2):
        asyncio.run(abuse.maybe_alert(event()))
    assert sent == []
    for _ in range(2):
        asyncio.run(abuse.maybe_alert(event()))
    assert len(sent) == 1
    assert sent[0]["incident_count"] == 3


def test_events_endpoint_checks_the_token(client, set_setting):
    set_setting("abuse_admin_token", "a" * 32)
    assert client.post("/api/admin/abuse-events", json={"token": "b" * 32}).json()["ok"] is False
    assert client.post("/api/admin/abuse-events", json={"token": "a" * 32}).json() == {"ok": True, "events": []}
