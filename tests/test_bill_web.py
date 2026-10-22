import asyncio

import httpx

from billbreaker.services import bill_web, web_search

BING = (
    "<rss><channel>"
    "<item><title>HB 1 video</title><link>https://www.youtube.com/watch?v=1</link></item>"
    "<item><title>HB 1 news</title><link>https://news.example.com/hb1</link></item>"
    "<item><title>Texas HB 1</title><link>https://capitol.texas.gov/BillLookup/History.aspx?Bill=HB1</link></item>"
    "<item><title>Texas HB 1</title><link>https://legiscan.com/TX/bill/HB1/2025</link></item>"
    "</channel></rss>"
)


def test_bill_numbers_match_their_common_spellings():
    pattern = bill_web.bill_pattern("HB 12")
    for text in ("HB 12", "H.B. 12", "HB12", "House Bill 12", "H.B. No. 12"):
        assert pattern.search(text), text
    for text in ("HB 120", "SB 12"):
        assert not pattern.search(text), text
    assert bill_web.bill_pattern("AB 5").search("Assembly Bill No. 5")


def test_search_results_are_read_from_both_engines():
    assert [r["url"] for r in web_search.parse_bing(BING)][2].startswith("https://capitol.texas.gov")
    ddg = '<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Flegiscan.com%2FTX%2Fbill%2FHB1">TX <b>HB1</b></a>'
    assert web_search.parse_ddg(ddg) == [{"url": "https://legiscan.com/TX/bill/HB1", "title": "TX HB1"}]


def test_a_state_bill_is_read_from_the_pages_that_name_it():
    body = "<html><body><h1>HB 1</h1><p>" + "Relating to school finance. " * 30 + "</p></body></html>"
    seen = []

    def handler(request):
        seen.append(request.url.host)
        if request.url.host == "www.bing.com":
            return httpx.Response(200, text=BING)
        if request.url.host == "news.example.com":
            return httpx.Response(200, text="<p>HB 10 passed</p>" * 50, headers={"content-type": "text/html"})
        return httpx.Response(200, text=body, headers={"content-type": "text/html; charset=utf-8"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await bill_web.fetch_web_text(client, "TX", "HB 1")

    text, url = asyncio.run(run())
    assert url.startswith("https://capitol.texas.gov")
    assert "Relating to school finance" in text
    assert "www.youtube.com" not in seen


def test_private_addresses_are_never_fetched():
    assert not bill_web._public("http://169.254.169.254/latest")
    assert not bill_web._public("http://localhost:3000/")
    assert not bill_web._public("file:///etc/passwd")
    assert bill_web._public("https://legiscan.com/TX/bill/HB1/2025")
