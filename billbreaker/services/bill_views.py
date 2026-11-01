"""
How often each bill's breakdown is opened, so the nightly refresh knows which
bills to keep ready. Only bill numbers are counted: no reader, IP or answers.
"""

import logging
from datetime import datetime, timedelta, timezone

from .. import db

log = logging.getLogger(__name__)

# A bill nobody opened for this long starts its count again, so old favorites fade out.
QUIET = timedelta(days=7)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def count(state: str, bill_no: str) -> None:
    now = _now()
    try:
        await db.execute(
            "INSERT INTO bill_views (state, bill_no, views, last_viewed) VALUES (?, ?, 1, ?) "
            "ON CONFLICT(state, bill_no) DO UPDATE SET "
            "views = CASE WHEN bill_views.last_viewed < ? THEN 1 ELSE bill_views.views + 1 END, "
            "last_viewed = excluded.last_viewed",
            (state, bill_no, now.isoformat(), (now - QUIET).isoformat()),
        )
    except Exception as exc:  # noqa: BLE001 - a missed count must never break a breakdown
        log.error("bill view count failed: %s", exc)


async def popular(limit: int) -> list[dict]:
    """Most opened bills that someone opened in the last week, most opened first."""
    return await db.query(
        "SELECT state, bill_no, views FROM bill_views WHERE last_viewed > ? "
        "ORDER BY views DESC, last_viewed DESC LIMIT ?",
        ((_now() - QUIET).isoformat(), limit),
    )
