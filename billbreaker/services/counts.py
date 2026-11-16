"""Site counters: one running total per name, plus a per-day tally for the stats page."""

import logging
from datetime import datetime, timedelta, timezone

from .. import db

log = logging.getLogger(__name__)


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


async def bump(name: str) -> None:
    """Adds one to a counter. A missed count must never break the request that made it."""
    try:
        await db.execute(
            "INSERT INTO counters (name, value) VALUES (?, 1) ON CONFLICT(name) DO UPDATE SET value = value + 1",
            (name,),
        )
        await db.execute(
            "INSERT INTO daily_counts (day, name, value) VALUES (?, ?, 1) "
            "ON CONFLICT(day, name) DO UPDATE SET value = value + 1",
            (_today(), name),
        )
    except Exception as exc:  # noqa: BLE001
        log.error("%s count failed: %s", name, exc)


async def total(name: str) -> int:
    row = await db.query_one("SELECT value FROM counters WHERE name = ?", (name,))
    return row["value"] if row else 0


async def by_day(days: int) -> dict[str, dict[str, int]]:
    """Counts per day for the last `days` days, newest first, zero filled."""
    start = datetime.now(timezone.utc).date() - timedelta(days=days - 1)
    rows = await db.query("SELECT day, name, value FROM daily_counts WHERE day >= ?", (start.isoformat(),))
    out = {(start + timedelta(days=i)).isoformat(): {} for i in reversed(range(days))}
    for r in rows:
        if r["day"] in out:
            out[r["day"]][r["name"]] = r["value"]
    return out
