"""GET /api/cron/prewarm: run once a day by Vercel Cron (see vercel.json)."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config import settings
from ..services import new_bills, prewarm

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/cron/prewarm")
async def prewarm_popular(request: Request):
    # Vercel sends this header when CRON_SECRET is set; without one, claim_run alone limits the job.
    if settings.cron_secret and request.headers.get("authorization") != f"Bearer {settings.cron_secret}":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    if not await prewarm.claim_run():
        return {"ok": True, "skipped": "ran recently"}
    try:
        listed = await new_bills.refresh()
    except Exception as exc:  # noqa: BLE001 - the refresh of known bills still runs
        log.error("new bills refresh failed: %s", type(exc).__name__)
        listed = {"error": type(exc).__name__}
    return {"ok": True, "new_bills": listed, "results": await prewarm.run()}
