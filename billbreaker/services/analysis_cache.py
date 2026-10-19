"""Seven-day cache of finished analyses, shared by every reader of the same bill text."""

import hashlib
import json
from datetime import datetime, timedelta, timezone

from .. import db

TTL = timedelta(days=7)


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def load_fresh(state: str, bill_no: str, text_hash: str) -> dict | None:
    row = await db.query_one(
        "SELECT payload FROM bill_analyses WHERE state = ? AND bill_no = ? AND text_hash = ? "
        "AND expires_at > ?",
        (state, bill_no, text_hash, _now().isoformat()),
    )
    return json.loads(row["payload"]) if row else None


async def load_latest(state: str, bill_no: str) -> tuple[dict, str] | None:
    """Last resort when the AI is down: newest analysis for this bill, even if stale."""
    row = await db.query_one(
        "SELECT payload, created_at FROM bill_analyses WHERE state = ? AND bill_no = ? "
        "ORDER BY created_at DESC LIMIT 1",
        (state, bill_no),
    )
    return (json.loads(row["payload"]), row["created_at"]) if row else None


async def save(state: str, bill_no: str, text_hash: str, title, source_url, sections: list[dict]) -> None:
    payload = json.dumps({"title": title, "sourceUrl": source_url, "sections": sections})
    now = _now()
    await db.execute(
        "INSERT INTO bill_analyses (state, bill_no, text_hash, title, source_url, payload, "
        "created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(state, bill_no, text_hash) DO UPDATE SET title = excluded.title, "
        "source_url = excluded.source_url, payload = excluded.payload, "
        "created_at = excluded.created_at, expires_at = excluded.expires_at",
        (state, bill_no, text_hash, title, source_url, payload, now.isoformat(), (now + TTL).isoformat()),
    )
