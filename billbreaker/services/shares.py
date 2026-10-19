"""Published, read-only snapshots of an analysis at /b/<slug>."""

import json
import secrets
from datetime import datetime, timezone

from .. import db

SLUG_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"
MAX_PAYLOAD_BYTES = 200_000


def random_slug(length: int = 8) -> str:
    return "".join(secrets.choice(SLUG_CHARS) for _ in range(length))


async def create(state: str, bill_no: str, title: str | None, source_url: str | None, payload: dict) -> str:
    body = json.dumps(payload)
    if len(body) > MAX_PAYLOAD_BYTES:
        raise ValueError(f"Payload too large (max {MAX_PAYLOAD_BYTES} bytes).")
    now = datetime.now(timezone.utc).isoformat()
    for _ in range(5):
        slug = random_slug()
        inserted = await db.query(
            "INSERT INTO shared_analyses (slug, state, bill_no, title, source_url, payload, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(slug) DO NOTHING RETURNING slug",
            (slug, state, bill_no, title, source_url, body, now),
        )
        if inserted:
            return slug
    raise RuntimeError("Could not generate share link, try again.")


async def get(slug: str) -> dict | None:
    row = await db.query_one("SELECT * FROM shared_analyses WHERE slug = ?", (slug,))
    if not row:
        return None
    out = dict(row)
    out["payload"] = json.loads(out["payload"] or "{}")
    return out
