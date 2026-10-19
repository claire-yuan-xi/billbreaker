import pytest


@pytest.mark.parametrize("path", ["/", "/bill?state=US&number=HR1", "/admin/ml", "/admin/abuse"])
def test_pages_render(client, path):
    res = client.get(path)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert "content-security-policy" in res.headers


def test_unknown_pages_and_shares_are_404(client):
    assert client.get("/nope").status_code == 404
    assert client.get("/b/abcdefgh").status_code == 404


def test_api_errors_are_json(client):
    res = client.get("/api/nope")
    assert res.status_code == 404
    assert res.json() == {"error": "Not Found"}


def test_share_round_trip(client):
    payload = {
        "state": "US",
        "bill_no": "HR1",
        "title": "A <b>test</b> bill",
        "source_url": "https://www.congress.gov/x",
        "payload": {"quick": {"tldr": "Plain words", "who_it_affects": [], "key_numbers": []}},
    }
    slug = client.post("/api/share", json=payload).json()["slug"]
    page = client.get(f"/b/{slug}")
    assert page.status_code == 200
    assert "Plain words" in page.text
    assert "<b>test</b>" not in page.text


def test_ml_rank_returns_rendered_tables(client):
    res = client.post(
        "/api/admin/ml/rank",
        json={"text": "SEC. 1. LOANS.\nStudent loans for college.", "profile": {"work": "student"}},
    ).json()
    assert res["ranked"][0]["section"] == "1"
    assert "LOANS" in res["tableHtml"]
    assert "student" in res["termsHtml"]


def test_ml_generate_needs_a_summary(client):
    assert client.post("/api/admin/ml/generate", json={"text": "x"}).status_code == 400


def test_ml_generate_personalizes_the_browser_summary(client, monkeypatch):
    async def fake(general, sections, profile):
        return "This bill funds student loans. It may help you as a student."

    monkeypatch.setattr("billbreaker.api.admin.personalize", fake)
    res = client.post(
        "/api/admin/ml/generate",
        json={
            "text": "SEC. 1. LOANS.\nFunds student loans for college.",
            "general": "Funds student loans for college.",
            "profile": {"work": "student"},
        },
    ).json()
    assert res["general"] == "Funds student loans for college."
    assert res["personalized"].startswith("This bill funds")
    assert "General summary" in res["html"]


def test_csp_allows_the_browser_model(client):
    csp = client.get("/admin/ml").headers["content-security-policy"]
    assert "'wasm-unsafe-eval'" in csp and "https://huggingface.co" in csp
