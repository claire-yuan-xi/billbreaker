"""
What the server is running and whether Gemini answers, so a failure on the live
site can be read from a browser. Never shows a key, only whether one is set.
"""

import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config import settings
from ..services import ai_client
from ..services.ai_client import AIError
from ..services.explain import breakdown
from ..services.rate_limit import bump, client_ip
from ..services.research import research_breakdown
from ..states import STATE_NAMES
from ..validation import normalize_bill_no

router = APIRouter()
SAMPLE = (
    "SEC. 1. SHORT TITLE. This Act may be cited as the Library Hours Act. SEC. 2. HOURS. Each public "
    "library that receives a grant under this Act shall stay open until 9 p.m. on weekdays. SEC. 3. "
    "FUNDING. There is authorized to be appropriated $5,000,000 for fiscal year 2027 to carry out this Act."
)
TTL = 120
_cache: dict[str, tuple[float, dict]] = {}


def _summary(title: str, sections: list[dict]) -> dict:
    return {"ok": True, "title": title, "sections": [s["event"] for s in sections]}


async def _check(kind: str, state: str, bill: str) -> dict:
    try:
        if kind == "ai":
            return {"models": await ai_client.probe()}
        if kind == "breakdown":
            return _summary(*await breakdown(SAMPLE, "Sample bill"))
        found = await research_breakdown(STATE_NAMES.get(state, state), bill, f"{state} {bill}")
        return _summary(*found[:2]) if found else {"ok": False, "error": "NOT_FOUND"}
    except AIError as exc:
        return {"ok": False, "error": exc.code}


@router.get("/api/status")
async def status(request: Request, check: str = "", state: str = "CA", bill: str = "AB 5"):
    out = {
        "commit": os.getenv("VERCEL_GIT_COMMIT_SHA", "")[:7] or "local",
        "keys": {
            "gemini": bool(settings.gemini_api_key),
            "openstates": bool(settings.openstates_api_key),
            "turso": bool(settings.turso_url),
        },
        "models": ai_client.models(),
    }
    if check not in ("ai", "breakdown", "research"):
        return out
    bill = normalize_bill_no(bill) or "AB 5"
    state = state.upper() if state.upper() in STATE_NAMES else "CA"
    key = f"{check}:{state}:{bill}"
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < TTL:
        return {**out, check: hit[1], "cached": True}
    rl = await bump(f"ip:{client_ip(request)}:status", 6, 600, endpoint="status")
    if not rl.allowed:
        return JSONResponse({**out, "error": "Too many checks. Try again later."}, status_code=429)
    result = await _check(check, state, bill)
    _cache[key] = (time.monotonic(), result)
    return {**out, check: result}
