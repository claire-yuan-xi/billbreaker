"""
What the server is running and whether Gemini answers, so a failure on the live
site can be read from a browser. Never shows a key, only whether one is set.
"""

import asyncio
import logging
import os
import re
import time

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config import settings
from ..services import ai_client
from ..services.ai_client import AIError
from ..services.bill_find import describe, resolve
from ..services.bill_sources import openstates_links, fetch_bill_text, find_openstates_bill
from ..services.documents import read_document
from ..services.bill_web import query_for
from ..services.explain import breakdown
from ..services.for_you import tailor
from ..services.rate_limit import bump, client_ip
from ..services.research import research_breakdown
from ..services.web_search import search
from ..states import STATE_NAMES
from ..validation import normalize_bill_no

log = logging.getLogger(__name__)
router = APIRouter()
SAMPLE_READER = {"state": "Texas", "age": "25-44", "work": "Teacher", "interests": "Libraries"}
SAMPLE_SECTIONS = [
    {
        "event": "quick_take",
        "data": {"tldr": "Libraries that take a federal grant stay open until 9 p.m. on weekdays.", "timeline": "2027"},
    }
]
SAMPLE = (
    "SEC. 1. SHORT TITLE. This Act may be cited as the Library Hours Act. SEC. 2. HOURS. Each public "
    "library that receives a grant under this Act shall stay open until 9 p.m. on weekdays. SEC. 3. "
    "FUNDING. There is authorized to be appropriated $5,000,000 for fiscal year 2027 to carry out this Act."
)
TTL = 120
_cache: dict[str, tuple[float, dict]] = {}
_running: dict[str, asyncio.Task] = {}


CHECKS = ("ai", "breakdown", "foryou", "research", "fetch", "openstates", "search", "bill", "resolve")


def _summary(title: str, sections: list[dict]) -> dict:
    return {"ok": True, "title": title, "sections": [s["event"] for s in sections]}


async def _bill(state: str, bill: str) -> dict:
    """The same path a search takes: official text if reachable, otherwise a web lookup."""
    fetched = await fetch_bill_text(state, bill)
    if fetched.text:
        title, sections = await breakdown(fetched.text, f"{state} {bill}")
        return {**_summary(title, sections), "source": fetched.source, "chars": len(fetched.text)}
    jurisdiction = "US federal" if state == "US" else STATE_NAMES.get(state, state)
    found = await research_breakdown(jurisdiction, bill, f"{state} {bill}")
    if not found:
        return {"ok": False, "error": "NOT_FOUND", "tried": fetched.tried}
    return {**_summary(*found[:2]), "source": "web", "tried": fetched.tried}


async def _resolve(state: str, queries: str) -> dict:
    """Which bill each search lands on. Searches are split by |, each "MI:1245" or just "1245"."""

    async def one(item: str) -> dict:
        where, _, typed = item.partition(":") if re.match(r"^[A-Z]{2}:", item) else ("", "", item)
        found = await resolve(where or state, typed)
        best = found.best
        return {"search": item, "bill": f"{best.state} {best.bill_no}" if best else None, **describe(found)}

    items = [i.strip() for i in queries.split("|") if i.strip()][:8]
    results = await asyncio.gather(*(one(i) for i in items))
    return {"ok": all(r["found"] for r in results), "results": list(results)}


async def _run(kind: str, state: str, bill: str, query: str = "") -> dict:
    if kind == "resolve":
        return await _resolve(state, query or bill)
    if kind == "ai":
        return {"models": await ai_client.probe()}
    if kind == "foryou":
        mine = await tailor("Sample bill", "Library Hours Act", SAMPLE_SECTIONS, SAMPLE_READER)
        return {"ok": bool(mine["summary"]), **mine}
    if kind == "breakdown":
        return _summary(*await breakdown(SAMPLE, "Sample bill"))
    if kind == "fetch":
        fetched = await fetch_bill_text(state, bill)
        text = fetched.text or ""
        return {
            "ok": bool(text),
            "source": fetched.source,
            "url": fetched.source_url,
            "chars": len(text),
            "start": text[:300],
            "tried": fetched.tried,
        }
    if kind == "openstates":
        async with httpx.AsyncClient(follow_redirects=True) as client:
            found, why = await find_openstates_bill(client, state, bill)
            if not found:
                return {"ok": False, "error": why}
            links = openstates_links(found)[:3]
            docs = [await read_document(client, url, 8) for url in links]
        return {
            "ok": True,
            "identifier": found.get("identifier"),
            "session": found.get("session"),
            "title": (found.get("title") or "")[:120],
            "versions": [
                {"date": v.get("date"), "links": [(l.get("media_type"), l.get("url")) for l in v.get("links") or []][:3]}
                for v in (found.get("versions") or [])[-2:]
            ],
            "links": [{"url": d.url, "status": d.status, "chars": len(d.text), "start": d.text[:80]} for d in docs],
        }
    if kind == "search":
        text = query or query_for(state, bill)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            results = await search(client, text)
        return {"ok": bool(results), "query": text, "results": [r["url"] for r in results[:8]]}
    if kind == "bill":
        return await _bill(state, bill)
    found = await research_breakdown(STATE_NAMES.get(state, state), bill, f"{state} {bill}")
    return _summary(*found[:2]) if found else {"ok": False, "error": "NOT_FOUND"}


async def _check(kind: str, state: str, bill: str, query: str = "") -> dict:
    started = time.monotonic()
    try:
        result = await _run(kind, state, bill, query)
    except AIError as exc:
        result = {"ok": False, "error": exc.code, "detail": exc.detail}
    except Exception as exc:  # noqa: BLE001 - the point of this page is to show the failure
        log.exception("status check %s failed", kind)
        result = {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:300]}
    return {**result, "seconds": round(time.monotonic() - started, 1)}


@router.get("/api/status")
async def status(
    request: Request, check: str = "", state: str = "CA", bill: str = "AB 5", q: str = ""
):
    out = {
        "commit": os.getenv("VERCEL_GIT_COMMIT_SHA", "")[:7] or "local",
        "keys": {
            "gemini": bool(settings.gemini_api_key),
            "openstates": bool(settings.openstates_api_key),
            "turso": bool(settings.turso_url),
        },
        "models": ai_client.models(),
    }
    if check not in CHECKS:
        return out
    bill = normalize_bill_no(bill) or "AB 5"
    state = state.upper() if state.upper() in STATE_NAMES else "CA"
    q = q.strip()[:400]
    key = f"{check}:{state}:{bill}:{q}"
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < TTL:
        return {**out, check: hit[1], "cached": True}
    if key in _running:
        return {**out, check: await asyncio.shield(_running[key]), "cached": True}
    try:
        rl = await bump(f"ip:{client_ip(request)}:status", 20, 600, endpoint="status")
    except Exception as exc:  # noqa: BLE001
        return {**out, "error": f"rate limit store failed: {type(exc).__name__}"}
    if not rl.allowed:
        return JSONResponse({**out, "error": "Too many checks. Try again later."}, status_code=429)
    # A check keeps running if the browser gives up, so asking again shows its result.
    task = asyncio.create_task(_check(check, state, bill, q))
    _running[key] = task
    task.add_done_callback(lambda t: _finish(key, t))
    return {**out, check: await asyncio.shield(task)}


def _finish(key: str, task: asyncio.Task) -> None:
    _running.pop(key, None)
    if not task.cancelled():
        _cache[key] = (time.monotonic(), task.result())
