def test_status_names_the_keys_without_showing_them(client, set_setting):
    set_setting("gemini_api_key", "secret-value")
    res = client.get("/api/status")
    assert res.json()["keys"]["gemini"] is True
    assert "secret-value" not in res.text


def test_a_gemini_failure_shows_google_s_message(client, monkeypatch):
    from billbreaker.api import status
    from billbreaker.services.ai_client import AIError

    async def refuse(*args):
        raise AIError("RATE_LIMIT", "lite-model 429: quota exceeded")

    monkeypatch.setattr(status, "research_breakdown", refuse)
    out = client.get("/api/status?check=research&state=TX&bill=HB 1").json()["research"]
    assert out["error"] == "RATE_LIMIT"
    assert out["detail"] == "lite-model 429: quota exceeded"
