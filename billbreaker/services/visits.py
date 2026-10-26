"""Counts site visits: every page load, not unique visitors."""

import logging

from .. import db

log = logging.getLogger(__name__)


async def count() -> None:
    try:
        await db.execute(
            "INSERT INTO counters (name, value) VALUES ('visits', 1) "
            "ON CONFLICT(name) DO UPDATE SET value = value + 1"
        )
    except Exception as exc:  # noqa: BLE001 - a missed count must never break a page
        log.error("visit count failed: %s", exc)


async def total() -> int:
    row = await db.query_one("SELECT value FROM counters WHERE name = 'visits'")
    return row["value"] if row else 0
