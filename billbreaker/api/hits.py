"""Click beacon from the browser: adds one to the clicks counter."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from ..services import counts
from ..services.rate_limit import bump, client_ip

router = APIRouter()
PER_IP = 300
WINDOW_S = 3600


@router.post("/api/hit")
async def hit(request: Request):
    limit = await bump(f"ip:{client_ip(request)}:hit", PER_IP, WINDOW_S, endpoint="hit")
    if limit.allowed:
        await counts.bump("clicks")
    return Response(status_code=204)
