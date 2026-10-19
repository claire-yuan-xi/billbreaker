"""
Optional cloud copy of saved bills, keyed by an opaque per-device id (UUID v4
held only in the reader's browser). Off unless CLOUD_SYNC is set.
"""

from datetime import datetime, timezone

from .. import db


def _iso(ts_ms: int | None = None) -> str:
    if ts_ms:
        return datetime.fromtimestamp(ts_ms / 1000, timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


async def pull(device_id: str) -> list[dict]:
    return await db.query(
        "SELECT state, bill_no, title, added_at FROM device_watchlist WHERE device_id = ? "
        "ORDER BY added_at DESC LIMIT 500",
        (device_id.lower(),),
    )


async def upsert(device_id: str, items: list[dict]) -> int:
    rows = [
        (
            device_id.lower(),
            i["state"].upper(),
            i["bill_no"].upper(),
            (i.get("title") or "")[:400],
            _iso(i.get("ts")),
        )
        for i in items
    ]
    await db.batch(
        "INSERT INTO device_watchlist (device_id, state, bill_no, title, added_at) "
        "VALUES (?, ?, ?, ?, ?) ON CONFLICT(device_id, state, bill_no) DO UPDATE SET "
        "title = excluded.title, added_at = excluded.added_at",
        rows,
    )
    return len(rows)


async def remove(device_id: str, state: str, bill_no: str) -> None:
    await db.execute(
        "DELETE FROM device_watchlist WHERE device_id = ? AND state = ? AND bill_no = ?",
        (device_id.lower(), state.upper(), bill_no.upper()),
    )
