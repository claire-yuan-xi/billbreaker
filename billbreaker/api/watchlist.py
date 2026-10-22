"""Device-keyed sync for saved bills. Security comes from the opaque device id plus IP limits."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..config import settings
from ..services import device_watchlist
from ..services.rate_limit import bump, client_ip

router = APIRouter(prefix="/api/watchlist")

DEVICE = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
STATE = r"^[A-Z]{2,4}$"
# "HB 12", "S 3000A", or an older federal bill with its Congress: "HR 5376 (117th)".
BILL = r"^[A-Za-z]{1,8}[.\s-]?\d{1,6}[A-Za-z]?(?: \(\d{1,3}(?:st|nd|rd|th)\))?$"


class Device(BaseModel):
    device_id: str = Field(pattern=DEVICE)


class Item(BaseModel):
    state: str = Field(pattern=STATE)
    bill_no: str = Field(pattern=BILL, max_length=20)
    title: str = Field(default="", max_length=400)
    ts: int | None = Field(default=None, ge=0)


class PushIn(Device, Item):
    pass


class RemoveIn(Device):
    state: str = Field(pattern=STATE)
    bill_no: str = Field(pattern=BILL, max_length=20)


class BulkIn(Device):
    items: list[Item] = Field(max_length=200)


def _require_cloud():
    if not settings.cloud_sync:
        raise HTTPException(503, "Cloud sync isn't set up yet.")


async def _throttle(request: Request, scope: str):
    ip = client_ip(request)
    if not (await bump(f"ip:{ip}:wl:{scope}:1m", 30, 60, endpoint="watchlist")).allowed:
        raise HTTPException(429, "Too many requests, slow down.")
    if not (await bump(f"ip:{ip}:wl:{scope}:1h", 400, 3600, endpoint="watchlist")).allowed:
        raise HTTPException(429, "Hourly sync limit reached.")


@router.get("/status")
async def status():
    return {"cloud": settings.cloud_sync}


@router.post("/pull")
async def pull(data: Device):
    if not settings.cloud_sync:
        return {"items": []}
    return {"items": await device_watchlist.pull(data.device_id)}


@router.post("/push")
async def push(data: PushIn, request: Request):
    _require_cloud()
    await _throttle(request, "push")
    await device_watchlist.upsert(data.device_id, [data.model_dump()])
    return {"ok": True}


@router.post("/remove")
async def remove(data: RemoveIn, request: Request):
    _require_cloud()
    await _throttle(request, "remove")
    await device_watchlist.remove(data.device_id, data.state, data.bill_no)
    return {"ok": True}


@router.post("/bulk")
async def bulk(data: BulkIn, request: Request):
    _require_cloud()
    await _throttle(request, "bulk")
    count = await device_watchlist.upsert(data.device_id, [i.model_dump() for i in data.items])
    return {"ok": True, "count": count}
