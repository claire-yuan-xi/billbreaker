import asyncio

import httpx

from billbreaker.services import bill_sources


def test_parses_bill_numbers():
    assert bill_sources.parse_bill_no("HR 1234") == ("HR", "1234")
    assert bill_sources.parse_bill_no("s.47") == ("S", "47")
    assert bill_sources.parse_bill_no("nonsense") is None


def test_ordinals():
    assert [bill_sources.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 119)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "119th",
    ]


def test_congress_text_is_fetched_and_stripped():
    page = "<html><body><pre>H. R. 1\n" + "SEC. 1. SHORT TITLE. " * 40 + "</pre></body></html>"

    def handler(request):
        return httpx.Response(200, text=page)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await bill_sources.fetch_congress_text(client, "HR1")

    result = asyncio.run(run())
    assert result is not None
    text, url = result
    assert text.startswith("H. R. 1")
    assert "congress.gov" in url


def test_openstates_targets_are_guarded():
    assert not bill_sources._openstates_target_ok("http://169.254.169.254/latest")
    assert not bill_sources._openstates_target_ok("file:///etc/passwd")


def test_openstates_prefers_web_pages_newest_first_then_pdfs_then_the_state_page():
    bill = {
        "versions": [
            {"date": "2025-01-10", "links": [{"url": "https://capitol.texas.gov/old.htm", "media_type": "text/html"}]},
            {
                "date": "2025-03-01",
                "links": [
                    {"url": "https://capitol.texas.gov/new.pdf", "media_type": "application/pdf"},
                    {"url": "http://capitol.texas.gov/new.htm", "media_type": "text/html"},
                ],
            },
        ],
        "sources": [{"url": "https://capitol.texas.gov/History.aspx?Bill=HB1"}, {"url": "http://10.0.0.1/x"}],
    }
    assert bill_sources.openstates_links(bill) == [
        "https://capitol.texas.gov/new.htm",
        "https://capitol.texas.gov/old.htm",
        "https://capitol.texas.gov/new.pdf",
        "https://capitol.texas.gov/History.aspx?Bill=HB1",
    ]


def test_undated_versions_keep_open_states_order():
    bill = {
        "versions": [
            {"date": "", "links": [{"url": "http://capitol.texas.gov/HB00001F.HTM", "media_type": "text/html"}]},
            {"date": "", "links": [{"url": "http://capitol.texas.gov/HB00001I.HTM", "media_type": "text/html"}]},
        ]
    }
    assert bill_sources.openstates_links(bill)[0] == "https://capitol.texas.gov/HB00001F.HTM"


def test_openstates_hosts_include_legislature_sites_off_gov():
    assert bill_sources._openstates_target_ok("https://legislature.maine.gov/x")
    assert bill_sources._openstates_target_ok("https://www.kslegislature.org/li/b2025_26/measures/hb2001/")
    assert not bill_sources._openstates_target_ok("https://example.com/x")


def fetch_govinfo(handler, bill_no="HR 1"):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
            return await bill_sources.fetch_govinfo_text(client, bill_no)

    return asyncio.run(run())


def test_govinfo_follows_its_link_service_to_the_newest_version():
    text = "<pre>[Congressional Bills 119th Congress]\nH.R.1\n" + "SEC. 1. SHORT TITLE. " * 40 + "</pre>"

    def handler(request):
        if request.url.path.startswith("/link/bills/") and request.url.path.endswith("/hr/1"):
            return httpx.Response(302, headers={"location": "https://www.govinfo.gov/content/pkg/BILLS-119hr1enr/html/BILLS-119hr1enr.htm"})
        return httpx.Response(200, text=text)

    found, url = fetch_govinfo(handler)
    assert "SEC. 1. SHORT TITLE." in found
    assert url == "https://www.govinfo.gov/app/details/BILLS-119hr1enr"


def test_a_govinfo_page_not_found_is_not_bill_text():
    missing = "<title>Page Not Found | GovInfo</title>" + "<p>Search our collections.</p>" * 50
    assert fetch_govinfo(lambda request: httpx.Response(200, text=missing)) is None
