"""GET /api/cron/prewarm: run once a day by Vercel Cron (see vercel.json)."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config import settings
from ..services import prewarm

router = APIRouter()


@router.get("/api/cron/prewarm")
async def prewarm_popular(request: Request):
    # Vercel sends this header when CRON_SECRET is set; without one, claim_run alone limits the job.
    if settings.cron_secret and request.headers.get("authorization") != f"Bearer {settings.cron_secret}":
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    if not await prewarm.claim_run():
        return {"ok": True, "skipped": "ran recently"}
    return {"ok": True, "results": await prewarm.run()}
