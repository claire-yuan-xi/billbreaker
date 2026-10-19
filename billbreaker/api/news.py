"""Live AP headlines and the resolver that turns feed links into apnews.com URLs."""

from urllib.parse import urlparse

import httpx
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, RedirectResponse

from ..services.ap_news import legislation_news
from ..services.google_news import decode_google_news_link, google_news_id
from ..services.links import is_allowed_resolve_host

router = APIRouter()
CACHE = {"Cache-Control": "public, max-age=3600"}


@router.get("/api/news")
async def news():
    return await legislation_news()


@router.get("/api/public/resolve")
async def resolve(url: str = ""):
    if not url:
        return PlainTextResponse("Bad request", status_code=400)
    try:
        target = urlparse(url)
    except ValueError:
        return PlainTextResponse("Invalid URL", status_code=400)
    if target.scheme not in ("http", "https") or not target.hostname:
        return PlainTextResponse("Invalid protocol", status_code=400)
    if not is_allowed_resolve_host(target.hostname):
        return PlainTextResponse("Forbidden host", status_code=403)

    if google_news_id(url):
        decoded = await decode_google_news_link(url)
        if decoded and is_allowed_resolve_host(urlparse(decoded).hostname or ""):
            return RedirectResponse(decoded, status_code=302, headers=CACHE)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            res = await client.get(url, headers={"User-Agent": "Mozilla/5.0 BillBreaker"})
    except httpx.HTTPError:
        return PlainTextResponse("Resolution failed", status_code=502)
    final = str(res.url)
    # Re-check the host after redirects before sending anyone there.
    if not is_allowed_resolve_host(urlparse(final).hostname or ""):
        return PlainTextResponse("Resolved to disallowed host", status_code=403)
    return RedirectResponse(final, status_code=302, headers=CACHE)
