"""POST /api/explain-bill: the AI breakdown, streamed as server-sent events or as one JSON reply."""

import json
import logging
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..config import settings
from ..services import analysis_cache
from ..services.bill_sources import fetch_bill_text
from ..services.explain import breakdown
from ..services.rate_limit import bump, client_ip
from ..services.render import render_section
from ..services.sanitize import sanitize_bill_text
from ..validation import BILL_NO, US_STATES

log = logging.getLogger(__name__)
router = APIRouter()

MAX_TEXT = 200_000
MIN_PASTED = 200
SSE_HEADERS = {"Cache-Control": "no-cache, no-transform", "Connection": "keep-alive"}


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def section_event(event: str, data: dict) -> str:
    """A section's data plus its rendered HTML, so the page only has to place it."""
    return sse(event, {**data, "html": render_section(event, data)})


def _flat(payload: dict, **extra) -> dict:
    out = {"title": payload.get("title"), "sourceUrl": payload.get("sourceUrl"), **extra, "html": {}}
    for section in payload.get("sections", []):
        out[section["event"]] = section["data"]
        out["html"][section["event"]] = render_section(section["event"], section["data"])
    return out


MESSAGES = {
    "RATE_LIMIT": "The free AI limit is used up for now. Try again in a few minutes.",
    "AI_NO_KEY": "AI is not set up on the server (no GEMINI_API_KEY).",
    "AI_BAD_KEY": "Gemini says the key on the server is not valid.",
    "AI_FORBIDDEN": "Gemini refused the key on the server (403).",
    "AI_TIMEOUT": "The AI took too long on this bill. Try again.",
}
# Retrying these at once in JSON mode cannot help and only spends quota.
NO_RETRY = {"RATE_LIMIT", "AI_NO_KEY", "AI_BAD_KEY", "AI_FORBIDDEN"}


def _friendly(code: str) -> str:
    return MESSAGES.get(code, f"AI analysis failed ({code}). Try again.")


async def _save_quietly(*args) -> None:
    try:
        await analysis_cache.save(*args)
    except Exception as exc:  # noqa: BLE001 - the reader still gets the analysis
        log.error("cache save failed: %s", exc)


@router.post("/api/explain-bill")
async def explain_bill(request: Request):
    try:
        body = await request.json()
    except ValueError:
        body = {}
    state = str(body.get("state") or "US").upper()[:4]
    bill_no = str(body.get("billNo") or "")[:40]
    text = str(body.get("text") or "")
    as_json = body.get("mode") == "json"

    def error(status: int, message: str, headers: dict | None = None):
        if as_json or status in (400, 413, 429):
            return JSONResponse({"error": message}, status_code=status, headers=headers)
        return StreamingResponse(
            iter([sse("error", {"message": message})]), media_type="text/event-stream"
        )

    if state not in US_STATES:
        return error(400, "Invalid state")
    if bill_no and not BILL_NO.match(bill_no):
        return error(400, "Invalid bill number")
    if len(text) > MAX_TEXT:
        return error(413, "Bill text too long")

    source_url = source = None
    tried: list[str] = []
    if len(text.strip()) < MIN_PASTED:
        if not bill_no:
            return error(400, "Paste the bill text on the Paste tab to analyze a non-federal bill.")
        fetched = await fetch_bill_text(state, bill_no)
        tried = fetched.tried
        if not fetched.text:
            note = (
                " OpenStates is not configured for state legislation, so paste the bill text on the Paste tab."
                if state != "US" and not settings.openstates_api_key
                else ""
            )
            label = " then ".join(tried) or "no sources"
            return error(
                502,
                f"Could not auto-fetch this bill (tried: {label}).{note} Paste the full text on the Paste tab.",
            )
        text, source_url, source = fetched.text, fetched.source_url, fetched.source

    text_hash = analysis_cache.hash_text(text)
    cache_bill = bill_no or f"paste-{text_hash[:8]}"
    source_meta = {"source": source, "tried": tried}

    # 1) Cache hit: free to anyone, no rate limit.
    try:
        cached = await analysis_cache.load_fresh(state, cache_bill, text_hash)
    except Exception as exc:  # noqa: BLE001
        log.error("cache lookup failed: %s", exc)
        cached = None
    if cached:
        if as_json:
            return JSONResponse(_flat(cached, cached=True, **source_meta), headers={"Cache-Control": "no-store"})

        def replay():
            yield sse("meta", {"title": cached["title"], "sourceUrl": cached["sourceUrl"], "cached": True, **source_meta})
            for s in cached["sections"]:
                yield section_event(s["event"], s["data"])
            yield sse("done", {"cached": True})

        return StreamingResponse(replay(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    # 2) Per-IP limits on cache misses, fail closed.
    ip = client_ip(request)
    for key, limit, window, message in (
        ("1m", 15, 60, "Too many requests. Try again in a minute."),
        ("10m", 40, 600, "Hourly limit reached. Try again shortly."),
    ):
        rl = await bump(f"ip:{ip}:explain:{key}", limit, window, endpoint="explain-bill")
        if not rl.allowed:
            return error(429, message, {"Retry-After": str(rl.retry_after)})

    bill = sanitize_bill_text(text)
    safe_state = re.sub(r"[^A-Z]", "", state)
    safe_bill = re.sub(r"[^A-Za-z0-9.\-\s]", "", bill_no)
    identifier = f"{safe_state} {safe_bill}".strip() or "Pasted bill"

    async def stale(code: str):
        """The last good analysis of this bill, with why it is being shown."""
        try:
            found = await analysis_cache.load_latest(state, cache_bill)
        except Exception as exc:  # noqa: BLE001
            log.error("stale lookup failed: %s", exc)
            return None
        if not found:
            return None
        payload, created_at = found
        reason = "rate_limited" if code == "RATE_LIMIT" else "ai_unavailable"
        return payload, {"cached": True, "cached_at": created_at, "cached_reason": reason}

    if as_json:
        try:
            title, sections = await breakdown(bill, identifier)
        except Exception as exc:  # noqa: BLE001 - every failure falls back to the last good analysis
            code = getattr(exc, "code", type(exc).__name__)
            log.error("json pipeline error: %s", code)
            old = await stale(code)
            if old:
                payload, flags = old
                return JSONResponse(_flat(payload, **flags, **source_meta), headers={"Cache-Control": "no-store"})
            return JSONResponse({"error": _friendly(code)}, status_code=503)
        await _save_quietly(state, cache_bill, text_hash, title, source_url, sections)
        payload = {"title": title, "sourceUrl": source_url, "sections": sections}
        return JSONResponse(_flat(payload, cached=False, **source_meta), headers={"Cache-Control": "no-store"})

    async def stream():
        yield sse("status", {"stage": "breakdown", "message": "Reading the bill and writing the breakdown"})
        try:
            title, sections = await breakdown(bill, identifier)
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", type(exc).__name__)
            log.error("sse pipeline error: %s", code)
            old = await stale(code)
            if old:
                payload, flags = old
                yield sse("meta", {"title": payload.get("title"), "sourceUrl": payload.get("sourceUrl"), **flags, **source_meta})
                for s in payload.get("sections", []):
                    yield section_event(s["event"], s["data"])
                yield sse("done", {"cached": True})
                return
            retry = {} if code in NO_RETRY else {"fallback": "json"}
            yield sse("error", {"message": _friendly(code), **retry})
            return
        yield sse("meta", {"title": title, "sourceUrl": source_url, "cached": False, **source_meta})
        for s in sections:
            yield section_event(s["event"], s["data"])
        yield sse("done", {"cached": False})
        await _save_quietly(state, cache_bill, text_hash, title, source_url, sections)

    return StreamingResponse(stream(), media_type="text/event-stream", headers=SSE_HEADERS)
