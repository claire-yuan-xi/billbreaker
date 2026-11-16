"""Reads the start of a GovInfo document through its link service, without downloading all of it."""

import httpx

from .text import strip_html

UA = "Mozilla/5.0 (compatible; BillBreaker/1.0)"
HEAD_BYTES = 60_000


async def read_head(client: httpx.AsyncClient, url: str, package: str, timeout: float) -> str | None:
    """The first part of the document as text, or None when GovInfo has no such package.

    A missing document answers 200 on the link page itself, with no package to redirect to.
    """
    try:
        async with client.stream("GET", url, timeout=timeout, headers={"User-Agent": UA}) as res:
            if res.status_code != 200 or package not in str(res.url):
                return None
            data = b""
            async for chunk in res.aiter_bytes():
                data += chunk
                if len(data) >= HEAD_BYTES:
                    break
    except httpx.HTTPError:
        return None
    return strip_html(data.decode("utf-8", "replace"))
