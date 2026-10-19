"""
Fixed-window rate limits stored in SQLite. Fails closed: if the store errors,
the caller is blocked, so an outage cannot be used to bypass throttling.
"""

import logging
import time
from dataclasses import dataclass

from starlette.requests import Request

from .. import db
from . import abuse

log = logging.getLogger(__name__)


@dataclass
class RateLimit:
    allowed: bool
    retry_after: int
    count: int


async def _bump(identifier: str, limit: int, window_s: int) -> RateLimit:
    """One atomic upsert: starts a new window when the old one has expired."""
    now = time.time()
    row = await db.query_one(
        "INSERT INTO rate_limits (identifier, window_start, count) VALUES (?, ?, 1) "
        "ON CONFLICT(identifier) DO UPDATE SET "
        "count = CASE WHEN ? - window_start >= ? THEN 1 ELSE count + 1 END, "
        "window_start = CASE WHEN ? - window_start >= ? THEN ? ELSE window_start END "
        "RETURNING window_start, count",
        (identifier, now, now, window_s, now, window_s, now),
    )
    start, count = row["window_start"], row["count"]
    retry = max(1, int(start + window_s - now + 0.999))
    return RateLimit(allowed=count <= limit, retry_after=retry, count=count)


async def count_only(identifier: str, window_s: int) -> int:
    """Counts hits in a window without ever blocking (used by the alert threshold)."""
    return (await _bump(identifier, 1_000_000_000, window_s)).count


async def bump(identifier: str, limit: int, window_s: int, endpoint: str | None = None) -> RateLimit:
    event = abuse.Event(identifier, limit, window_s, 0, "exception", endpoint)
    try:
        result = await _bump(identifier, limit, window_s)
    except Exception as exc:  # noqa: BLE001 - any store failure must block, not crash
        log.error("rate limit store error: %s", exc)
        await abuse.record(event)
        await abuse.maybe_alert(event)
        return RateLimit(allowed=False, retry_after=60, count=0)
    event.count = result.count
    if not result.allowed:
        event.reason = "limit_exceeded"
        await abuse.record(event)
        await abuse.maybe_alert(event)
    elif result.count >= int(limit * 0.8):
        event.reason = "near_limit"
        await abuse.record(event)
    return result


def client_ip(request: Request) -> str:
    """The caller's address as the hosting proxy saw it.

    Hosting proxies append (or, on Vercel, overwrite with) the real client in
    X-Forwarded-For, so only the last entry is trusted; earlier ones can be forged.
    """
    hops = [h.strip() for h in (request.headers.get("x-forwarded-for") or "").split(",") if h.strip()]
    candidate = hops[-1] if hops else (request.client.host if request.client else "")
    return candidate if candidate and len(candidate) < 64 else "unknown"
