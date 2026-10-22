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
    page = "<html><body><pre>" + "SEC. 1. SHORT TITLE. " * 40 + "</pre></body></html>"

    def handler(request):
        return httpx.Response(200, text=page)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await bill_sources.fetch_congress_text(client, "HR1")

    result = asyncio.run(run())
    assert result is not None
    text, url = result
    assert text.startswith("SEC. 1. SHORT TITLE.")
    assert "congress.gov" in url


def test_openstates_targets_are_guarded():
    assert not bill_sources._openstates_target_ok("http://169.254.169.254/latest")
    assert not bill_sources._openstates_target_ok("file:///etc/passwd")


def test_openstates_prefers_the_newest_web_page_then_pdf_then_the_state_page():
    bill = {
        "versions": [
            {"date": "2025-01-10", "links": [{"url": "https://capitol.texas.gov/old.htm", "media_type": "text/html"}]},
            {
                "date": "2025-03-01",
                "links": [
                    {"url": "https://capitol.texas.gov/new.pdf", "media_type": "application/pdf"},
                    {"url": "https://capitol.texas.gov/new.htm", "media_type": "text/html"},
                ],
            },
        ],
        "sources": [{"url": "https://capitol.texas.gov/History.aspx?Bill=HB1"}, {"url": "http://10.0.0.1/x"}],
    }
    assert bill_sources._openstates_links(bill) == [
        "https://capitol.texas.gov/new.htm",
        "https://capitol.texas.gov/old.htm",
        "https://capitol.texas.gov/new.pdf",
        "https://capitol.texas.gov/History.aspx?Bill=HB1",
    ]


def test_openstates_hosts_include_legislature_sites_off_gov():
    assert bill_sources._openstates_target_ok("https://legislature.maine.gov/x")
    assert bill_sources._openstates_target_ok("https://www.kslegislature.org/li/b2025_26/measures/hb2001/")
    assert not bill_sources._openstates_target_ok("https://example.com/x")
