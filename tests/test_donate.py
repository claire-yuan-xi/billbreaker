from billbreaker.config import settings
from billbreaker.services import donate


def test_donate_page_shows_amounts_and_header_link(client):
    page = client.get("/donate")
    assert page.status_code == 200
    for amount in ("$1", "$2", "$5", "$10"):
        assert amount in page.text
    assert "checkout.stripe.com" in page.headers["content-security-policy"]
    assert 'href="/donate"' in client.get("/").text


def test_donate_without_key_returns_to_page(client):
    res = client.post("/donate", data={"amount": "5"}, follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/donate?error=1"


def test_donate_rejects_other_amounts(client):
    object.__setattr__(settings, "stripe_secret_key", "sk_test_x")
    try:
        res = client.post("/donate", data={"amount": "7"}, follow_redirects=False)
    finally:
        object.__setattr__(settings, "stripe_secret_key", "")
    assert res.headers["location"] == "/donate?error=1"


def test_donate_redirects_to_checkout(client, monkeypatch):
    seen = {}

    async def fake(dollars, site):
        seen["args"] = (dollars, site)
        return "https://checkout.stripe.com/c/pay/cs_test_1"

    monkeypatch.setattr("billbreaker.api.donate.checkout_url", fake)
    res = client.post("/donate", data={"amount": "10"}, follow_redirects=False)
    assert res.headers["location"].startswith("https://checkout.stripe.com/")
    assert seen["args"][0] == 10


def test_thanks_page(client):
    assert "Thank you" in client.get("/donate?thanks=1").text


def test_amounts_are_fixed():
    assert donate.AMOUNTS == (1, 2, 5, 10)


def test_stripe_reason_is_kept_without_the_key(set_setting, monkeypatch):
    import asyncio

    import httpx
    import pytest

    from billbreaker.services import donate

    set_setting("stripe_secret_key", "sk_live_abc")

    def reply(request):
        msg = "Invalid API Key provided: sk_live_****abcd"
        return httpx.Response(401, json={"error": {"message": msg}})

    real = httpx.AsyncClient
    monkeypatch.setattr(donate.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(reply), **kw))
    with pytest.raises(donate.DonateError) as err:
        asyncio.run(donate.checkout_url(1, "https://billbreaker.org"))
    assert "Invalid API Key provided" in str(err.value) and "abcd" not in str(err.value)
