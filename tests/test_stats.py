import asyncio

from billbreaker.services import counts
from billbreaker.services.stats import BASELINE


def test_stats_page_adds_the_baseline_to_live_counts(client):
    client.get("/")
    client.get("/")
    client.post("/api/hit")
    page = client.get("/stats")
    assert page.status_code == 200
    assert f"{BASELINE['visits'] + 2:,}" in page.text
    assert "noindex" in page.text


def test_the_stats_page_is_not_itself_a_visit(client):
    client.get("/stats")
    assert client.get("/api/status").json()["visits"] == 0


def test_a_click_is_counted_in_total_and_by_day(client):
    assert client.post("/api/hit").status_code == 204
    assert asyncio.run(counts.total("clicks")) == 1
    today = next(iter(asyncio.run(counts.by_day(1)).values()))
    assert today == {"clicks": 1}


def test_public_pages_load_the_click_counter_and_admin_pages_do_not(client):
    assert "js/lib/clicks.js" in client.get("/").text
    assert "js/lib/clicks.js" not in client.get("/admin/abuse").text
