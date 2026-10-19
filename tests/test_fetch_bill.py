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
