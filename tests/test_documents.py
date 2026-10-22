import asyncio

import httpx

from billbreaker.services import documents


def read(response: httpx.Response) -> documents.Document:
    async def run():
        transport = httpx.MockTransport(lambda request: response)
        async with httpx.AsyncClient(transport=transport) as client:
            return await documents.read_document(client, "https://example.gov/bill", 5)

    return asyncio.run(run())


def test_a_page_keeps_its_html_for_following_links():
    doc = read(httpx.Response(200, text="<p>HB 1</p><a href='/text.htm'>t</a>", headers={"content-type": "text/html"}))
    assert doc.text.startswith("HB 1")
    assert "href" in doc.html


def test_a_broken_pdf_reads_as_empty():
    doc = read(httpx.Response(200, content=b"%PDF-1.7 not really", headers={"content-type": "application/pdf"}))
    assert doc.text == ""


def test_other_files_are_skipped():
    assert read(httpx.Response(200, content=b"PK\x03\x04", headers={"content-type": "application/zip"})).text == ""
    assert read(httpx.Response(404, text="missing")).text == ""
