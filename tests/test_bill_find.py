import asyncio
from urllib.parse import quote

import httpx
import pytest

from billbreaker.services import bill_find
from billbreaker.services.bill_find import Match, federal_from_url, resolve, state_from_url
from billbreaker.services.bill_sources import current_congress

NOW = current_congress()


@pytest.fixture
def web(monkeypatch):
    """Routes every request resolve makes to a handler the test sets."""
    routes = {}
    real = httpx.AsyncClient

    def handler(request: httpx.Request):
        for match, answer in routes.items():
            if match in str(request.url):
                return answer(request) if callable(answer) else answer
        return httpx.Response(404)

    monkeypatch.setattr(bill_find.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return routes


def govinfo(congress, kind, number):
    return f"govinfo.gov/link/bills/{congress}/{kind}/{number}?"


def printed(congress, kind, number):
    package = f"BILLS-{congress}{kind}{number}ih"
    return httpx.Response(302, headers={"Location": f"https://www.govinfo.gov/content/pkg/{package}/html/{package}.htm"})


def ddg(*links):
    rows = "".join(
        f'<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg={quote(url, safe="")}">{title}</a>'
        for url, title in links
    )
    return httpx.Response(200, text=f"<html>{rows}</html>")


def test_reads_bills_from_links():
    assert federal_from_url("https://www.congress.gov/bill/119th-congress/senate-bill/5/text") == (119, "S", "5")
    assert federal_from_url("https://www.govtrack.us/congress/bills/117/hr5376") == (117, "HR", "5376")
    assert federal_from_url("https://www.govinfo.gov/app/details/BILLS-117hr5376enr") == (117, "HR", "5376")
    assert state_from_url("https://legiscan.com/MI/bill/SB1245/2025", "MI") == "SB 1245"
    assert state_from_url("https://legiscan.com/TX/bill/SB1245/2025", "MI") is None


def test_a_federal_bill_with_its_chamber_needs_no_lookup():
    found = asyncio.run(resolve("US", "H.R. 1"))
    assert found.best == Match("US", "HR 1")
    # A state chamber with no state picked is not a Congress bill.
    assert asyncio.run(resolve("US", "AB 5")).best is None


def test_a_federal_number_finds_the_house_bill_first(web):
    web[govinfo(NOW, "hr", 1245)] = printed(NOW, "hr", 1245)
    web[govinfo(NOW, "s", 1245)] = printed(NOW, "s", 1245)
    web["/content/pkg/"] = httpx.Response(200, text="ok")
    found = asyncio.run(resolve("US", "1245"))
    assert found.best == Match("US", "HR 1245")
    assert found.others == [Match("US", "S 1245")]


def test_a_number_only_in_the_last_congress_carries_it(web):
    web[govinfo(NOW - 1, "s", 77)] = printed(NOW - 1, "s", 77)
    web["/content/pkg/"] = httpx.Response(200, text="ok")
    web["govinfo.gov/link/"] = httpx.Response(200, text="Page Not Found")
    found = asyncio.run(resolve("US", "77"))
    assert found.best.bill_no == f"S 77 ({NOW - 1}th)"


def test_a_state_number_without_a_chamber_asks_open_states(web, set_setting):
    set_setting("openstates_api_key", "k")
    asked = []

    def openstates(request):
        asked.append(request.url.params.get_list("identifier"))
        return httpx.Response(200, json={"results": [{"id": "b1", "identifier": "SB 1245", "title": "Schools"}]})

    web["v3.openstates.org"] = openstates
    found = asyncio.run(resolve("US", "MI 1245"))
    assert found.best == Match("MI", "SB 1245", "Schools")
    assert "HB 1245" in asked[0] and "SB 1245" in asked[0] and len(asked[0]) <= 20


def test_a_missing_state_bill_suggests_others_with_its_number(web, set_setting):
    set_setting("openstates_api_key", "k")

    def openstates(request):
        ids = request.url.params.get_list("identifier")
        rows = [{"id": "b1", "identifier": "SB 1245", "title": "Schools"}] if len(ids) > 1 else []
        return httpx.Response(200, json={"results": rows})

    web["v3.openstates.org"] = openstates
    found = asyncio.run(resolve("MI", "HB 1245"))
    assert found.best is None
    assert found.others == [Match("MI", "SB 1245", "Schools")]


def test_a_federal_bill_is_found_by_name(web):
    web["duckduckgo.com"] = ddg(
        (
            "https://www.congress.gov/bill/119th-congress/senate-bill/5",
            "S.5 - 119th Congress (2025-2026): Laken Riley Act | Congress.gov | Library of Congress",
        ),
    )
    found = asyncio.run(resolve("US", "Laken Riley Act", use_ai=False))
    assert found.best == Match("US", "S 5", "Laken Riley Act")


def bill_text(short_title):
    return httpx.Response(200, html=f"<pre>SECTION 1. SHORT TITLE. This Act may be cited as the ``{short_title}''.</pre>")


def test_a_named_bill_must_carry_that_name(web):
    web["duckduckgo.com"] = ddg(
        ("https://www.congress.gov/bill/119th-congress/house-bill/191/text/ih/pdf", "PDF Th St Congress Session H. R. 191"),
        ("https://www.congress.gov/bill/119th-congress/house-bill/300", "H.R.300 - 119th Congress (2025-2026): Inflation Reduction Act Repeal Act"),
        ("https://www.congress.gov/bill/117th-congress/house-bill/5376", "H.R.5376 - 117th Congress (2021-2022): Inflation Reduction Act of 2022"),
    )
    web[govinfo(NOW, "hr", 191)] = printed(NOW, "hr", 191)
    web[f"BILLS-{NOW}hr191"] = bill_text("Lower Costs Act")
    found = asyncio.run(resolve("US", "Inflation Reduction Act", use_ai=False))
    assert found.best == Match("US", "HR 5376 (117th)", "Inflation Reduction Act of 2022")
    assert found.others == [Match("US", "HR 300", "Inflation Reduction Act Repeal Act")]


def test_a_guess_is_kept_only_when_govinfo_has_the_bill(web, monkeypatch):
    web["duckduckgo.com"] = ddg()
    web[govinfo(117, "hr", 5376)] = printed(117, "hr", 5376)
    web["/content/pkg/"] = bill_text("Inflation Reduction Act of 2022")

    async def guess(system, user, schema, light=False):
        assert "<search>Inflation Reduction Act</search>" in user
        return {"known": True, "bill_no": "H.R. 5376", "congress": 117, "title": "Inflation Reduction Act of 2022"}

    monkeypatch.setattr(bill_find, "call_ai", guess)
    found = asyncio.run(resolve("US", "Inflation Reduction Act"))
    assert found.best == Match("US", "HR 5376 (117th)", "Inflation Reduction Act of 2022")

    async def wrong(system, user, schema, light=False):
        return {"known": True, "bill_no": "HR 99999", "congress": 117, "title": "Made up"}

    monkeypatch.setattr(bill_find, "call_ai", wrong)
    web["govinfo.gov/link/"] = httpx.Response(200, text="Page Not Found")
    assert asyncio.run(resolve("US", "Some Made Up Act")).best is None


def test_bill_meta_answers_with_the_bill_it_settled_on(client):
    body = client.post("/api/bill-meta", json={"state": "US", "billNo": "h.r. 1"}).json()
    assert body["found"] and body["best"]["billNo"] == "HR 1" and body["id"] == "HR 1"
    assert body["place"] == "United States Federal"


def test_bill_meta_says_when_nothing_matches(client, monkeypatch):
    from billbreaker.api import bills

    async def nothing(state, raw, use_ai=True):
        return bill_find.Found(bill_find.parse_query(state, raw))

    monkeypatch.setattr(bills, "resolve", nothing)
    body = client.post("/api/bill-meta", json={"state": "US", "billNo": "MI 1245"}).json()
    assert body["found"] is False and body["jurisdiction"] == "MI" and body["others"] == []


@pytest.mark.parametrize(
    "title, clean",
    [
        ("S.5 - 119th Congress (2025-2026): Laken Riley Act | Congress.gov | Library of Congress", "Laken Riley Act"),
        ("H.R.7511 - Laken Riley Act 118th Congress (2023-2024)", "Laken Riley Act"),
        ("Congress.gov", ""),
        ("PDF H. R. 29 - Congress.gov", ""),
        ("Bill Text: MI SB1245 | 2023-2024 | 102nd Legislature | LegiScan", ""),
    ],
)
def test_search_result_titles_are_cleaned(title, clean):
    assert bill_find._clean_title(title) == clean


def test_gemini_names_the_act_when_the_web_only_finds_bills_about_it(web, monkeypatch):
    web["duckduckgo.com"] = ddg(
        ("https://www.congress.gov/bill/119th-congress/house-bill/300", "H.R.300 - 119th Congress (2025-2026): Inflation Reduction Act Repeal Act"),
    )
    web[govinfo(117, "hr", 5376)] = printed(117, "hr", 5376)
    web["/content/pkg/"] = bill_text("Inflation Reduction Act of 2022")

    async def guess(system, user, schema, light=False):
        return {"known": True, "bill_no": "HR 5376", "congress": 117, "title": "Inflation Reduction Act"}

    monkeypatch.setattr(bill_find, "call_ai", guess)
    found = asyncio.run(resolve("US", "Inflation Reduction Act"))
    assert found.best.bill_no == "HR 5376 (117th)"
    assert [m.bill_no for m in found.others] == ["HR 300"]
