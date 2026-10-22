import asyncio

from urllib.parse import quote

import httpx

from billbreaker.services import bill_web, web_search

def ddg_result(url: str, title: str) -> str:
    return f'<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg={quote(url, safe="")}">{title}</a>'


SEARCH = "".join(
    ddg_result(url, title)
    for url, title in (
        ("https://www.youtube.com/watch?v=1", "HB 1 video"),
        ("https://news.example.com/hb1", "HB 1 news"),
        ("https://capitol.texas.gov/BillLookup/History.aspx?Bill=HB1", "Texas HB 1"),
        ("https://legiscan.com/TX/bill/HB1/2025", "Texas HB 1"),
    )
)
BILL_PAGE = "<html><body><h1>HB 1</h1><p>" + "Relating to school finance. " * 30 + "</p></body></html>"


def test_bill_numbers_match_their_common_spellings():
    pattern = bill_web.bill_pattern("HB 12")
    for text in ("HB 12", "H.B. 12", "HB12", "House Bill 12", "H.B. No. 12"):
        assert pattern.search(text), text
    for text in ("HB 120", "SB 12"):
        assert not pattern.search(text), text
    assert bill_web.bill_pattern("AB 5").search("Assembly Bill No. 5")


def run_fetch(handler, state="TX", bill_no="HB 1"):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await bill_web.fetch_web_text(client, state, bill_no)

    return asyncio.run(run())


def test_search_results_are_unwrapped():
    ddg = '<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Flegiscan.com%2FTX%2Fbill%2FHB1">TX <b>HB1</b></a>'
    assert web_search.parse_ddg(ddg) == [{"url": "https://legiscan.com/TX/bill/HB1", "title": "TX HB1"}]


def test_a_legislature_page_is_followed_to_the_bill_text():
    page = BILL_PAGE.replace("</body>", '<a href="/tlodocs/89R/billtext/html/HB00001I.htm">Text</a></body>')
    text_page = "<pre>" + "H.B. No. 1 AN ACT relating to the budget. " * 30 + "</pre>"

    def handler(request):
        if request.url.host == "html.duckduckgo.com":
            return httpx.Response(200, text=SEARCH)
        if request.url.path.endswith("HB00001I.htm"):
            return httpx.Response(200, text=text_page, headers={"content-type": "text/html"})
        if request.url.host == "capitol.texas.gov":
            return httpx.Response(200, text=page, headers={"content-type": "text/html"})
        return httpx.Response(404)

    text, url = run_fetch(handler)
    assert url == "https://capitol.texas.gov/tlodocs/89R/billtext/html/HB00001I.htm"
    assert "AN ACT relating to the budget" in text


def test_a_state_bill_is_read_from_the_pages_that_name_it():
    seen = []

    def handler(request):
        seen.append(request.url.host)
        if request.url.host == "html.duckduckgo.com":
            return httpx.Response(200, text=SEARCH)
        if request.url.host == "news.example.com":
            return httpx.Response(200, text="<p>HB 10 passed</p>" * 50, headers={"content-type": "text/html"})
        return httpx.Response(200, text=BILL_PAGE, headers={"content-type": "text/html; charset=utf-8"})

    text, url = run_fetch(handler)
    assert url.startswith("https://capitol.texas.gov")
    assert "Relating to school finance" in text
    assert "www.youtube.com" not in seen
    assert "legiscan.com" not in seen


def test_private_addresses_are_never_fetched():
    assert not bill_web._public("http://169.254.169.254/latest")
    assert not bill_web._public("http://localhost:3000/")
    assert not bill_web._public("file:///etc/passwd")
    assert bill_web._public("https://legiscan.com/TX/bill/HB1/2025")
