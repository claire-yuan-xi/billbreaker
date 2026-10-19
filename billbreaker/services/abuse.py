"""
Abuse monitoring around the rate limits: one JSON log line per event, a row in
abuse_events for the admin page, and an optional webhook after a sustained burst.
Nothing here may ever fail a user request.
"""

import asyncio
import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from ..config import settings
from .. import db

log = logging.getLogger("billbreaker.abuse")


@dataclass
class Event:
    identifier: str
    limit: int
    window_s: int
    count: int
    reason: str
    endpoint: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def record(event: Event) -> None:
    log.warning(
        "[abuse] %s",
        json.dumps(
            {
                "evt": "abuse",
                "ts": _now(),
                "identifier": event.identifier,
                "endpoint": event.endpoint,
                "limit": event.limit,
                "window_s": event.window_s,
                "count": event.count,
                "reason": event.reason,
            }
        ),
    )
    try:
        await db.execute(
            "INSERT INTO abuse_events (ts, identifier, endpoint, reason, count, limit_value, "
            "window_seconds, meta) VALUES (?, ?, ?, ?, ?, ?, ?, '{}')",
            (_now(), event.identifier, event.endpoint, event.reason, event.count, event.limit, event.window_s),
        )
    except Exception as exc:  # noqa: BLE001
        log.error("abuse event insert failed: %s", exc)


async def recent_events(limit: int) -> list[dict]:
    return await db.query(
        "SELECT id, ts, identifier, endpoint, reason, count, limit_value, window_seconds "
        "FROM abuse_events ORDER BY id DESC LIMIT ?",
        (limit,),
    )


def webhook_url() -> str | None:
    url = settings.abuse_alert_webhook_url
    if not url:
        return None
    try:
        return url if urlparse(url).scheme == "https" else None
    except ValueError:
        return None


async def post_with_retry(url: str, body: dict, attempts: int = 3, base_delay: float = 0.25, timeout: float = 4) -> dict:
    """POST with bounded retries; 5xx, 408 and 429 retry, other 4xx do not."""
    attempts = max(1, min(5, attempts))
    last = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        for i in range(attempts):
            try:
                res = await client.post(url, json=body)
                if res.is_success:
                    return {"ok": True, "status": res.status_code, "attempts": i + 1}
                if not (res.status_code >= 500 or res.status_code in (408, 429)):
                    return {"ok": False, "status": res.status_code, "attempts": i + 1}
                last = f"http_{res.status_code}"
            except httpx.HTTPError as exc:
                last = type(exc).__name__
            if i < attempts - 1:
                await asyncio.sleep(base_delay * 2**i + random.random() * base_delay)
    return {"ok": False, "attempts": attempts, "error": last}


async def maybe_alert(event: Event) -> None:
    url = webhook_url()
    if not url:
        return
    from .rate_limit import _bump, count_only

    try:
        incidents = await count_only(f"abuse-incident:{event.identifier}", 3600)
        if incidents < settings.abuse_alert_threshold:
            return
        if not (await _bump(f"abuse-alert:{event.identifier}", 1, settings.abuse_alert_cooldown_s)).allowed:
            return
        result = await post_with_retry(
            url,
            {
                "text": (
                    f"[abuse-alert] {event.identifier} hit rate limits {incidents}x in last hour "
                    f"(reason={event.reason}, endpoint={event.endpoint or '?'}, "
                    f"limit={event.limit}/{event.window_s}s)"
                ),
                "identifier": event.identifier,
                "endpoint": event.endpoint,
                "incident_count": incidents,
                "threshold": settings.abuse_alert_threshold,
                "window_hours": 1,
                "reason": event.reason,
                "limit": event.limit,
                "window_seconds": event.window_s,
                "ts": _now(),
            },
        )
        if not result["ok"]:
            log.error("abuse webhook failed after %s attempts", result["attempts"])
    except Exception as exc:  # noqa: BLE001
        log.error("abuse alert failed: %s", exc)
