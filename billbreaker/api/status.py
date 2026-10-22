"""
What the server is running and whether Gemini answers, so a failure on the live
site can be read from a browser. Never shows a key, only whether one is set.
"""

import asyncio
import logging
import os
import time

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import db
from ..config import settings
from ..services import ai_client
from ..services.ai_client import AIError
from ..services.bill_sources import fetch_bill_text
from ..services.bill_web import query_for
from ..services.explain import breakdown
from ..services.rate_limit import bump, client_ip
from ..services.research import research_breakdown
from ..services.web_search import search
from ..states import STATE_NAMES
from ..validation import normalize_bill_no

log = logging.getLogger(__name__)
router = APIRouter()
SAMPLE = (
    "SEC. 1. SHORT TITLE. This Act may be cited as the Library Hours Act. SEC. 2. HOURS. Each public "
    "library that receives a grant under this Act shall stay open until 9 p.m. on weekdays. SEC. 3. "
    "FUNDING. There is authorized to be appropriated $5,000,000 for fiscal year 2027 to carry out this Act."
)
TTL = 120
_cache: dict[str, tuple[float, dict]] = {}


CHECKS = ("ai", "breakdown", "research", "fetch", "search", "bill", "wait", "waited")


def _summary(title: str, sections: list[dict]) -> dict:
    return {"ok": True, "title": title, "sections": [s["event"] for s in sections]}


async def _mark(name: str, seconds: int) -> None:
    await db.execute(
        "INSERT INTO rate_limits (identifier, window_start, count) VALUES (?, ?, 1) "
        "ON CONFLICT(identifier) DO UPDATE SET window_start = excluded.window_start, count = 1",
        (f"status-wait:{seconds}:{name}", time.time()),
    )


async def _waited(seconds: int) -> dict:
    """When the last wait check started and finished, even if the browser gave up first."""
    out = {}
    for name in ("start", "end"):
        row = await db.query_one("SELECT window_start FROM rate_limits WHERE identifier = ?", (f"status-wait:{seconds}:{name}",))
        out[name] = round(row["window_start"]) if row else None
    out["finished"] = bool(out["start"] and out["end"] and out["end"] >= out["start"])
    return out


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


async def _run(kind: str, state: str, bill: str, seconds: int) -> dict:
    if kind == "wait":
        # Shows how long the host lets one request run before it is cut off.
        await _mark("start", seconds)
        await asyncio.sleep(seconds)
        await _mark("end", seconds)
        return {"ok": True, "waited": seconds}
    if kind == "waited":
        return await _waited(seconds)
    if kind == "ai":
        return {"models": await ai_client.probe()}
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
    if kind == "search":
        async with httpx.AsyncClient(follow_redirects=True) as client:
            engine, results = await search(client, query_for(state, bill))
        return {"ok": bool(results), "engine": engine, "results": [r["url"] for r in results[:8]]}
    if kind == "bill":
        return await _bill(state, bill)
    found = await research_breakdown(STATE_NAMES.get(state, state), bill, f"{state} {bill}")
    return _summary(*found[:2]) if found else {"ok": False, "error": "NOT_FOUND"}


async def _check(kind: str, state: str, bill: str, seconds: int) -> dict:
    started = time.monotonic()
    try:
        result = await _run(kind, state, bill, seconds)
    except AIError as exc:
        result = {"ok": False, "error": exc.code, "detail": exc.detail}
    except Exception as exc:  # noqa: BLE001 - the point of this page is to show the failure
        log.exception("status check %s failed", kind)
        result = {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:300]}
    return {**result, "seconds": round(time.monotonic() - started, 1)}


@router.get("/api/status")
async def status(request: Request, check: str = "", state: str = "CA", bill: str = "AB 5", seconds: int = 5):
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
    seconds = max(1, min(seconds, 90))
    key = f"{check}:{state}:{bill}:{seconds}"
    hit = _cache.get(key)
    if hit and check != "waited" and time.monotonic() - hit[0] < TTL:
        return {**out, check: hit[1], "cached": True}
    try:
        rl = await bump(f"ip:{client_ip(request)}:status", 20, 600, endpoint="status")
    except Exception as exc:  # noqa: BLE001
        return {**out, "error": f"rate limit store failed: {type(exc).__name__}"}
    if not rl.allowed:
        return JSONResponse({**out, "error": "Too many checks. Try again later."}, status_code=429)
    result = await _check(check, state, bill, seconds)
    _cache[key] = (time.monotonic(), result)
    return {**out, check: result}
