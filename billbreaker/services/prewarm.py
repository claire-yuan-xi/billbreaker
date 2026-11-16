"""
Nightly refresh: writes breakdowns for bills on the floor of Congress, rewriting
them when a new version is printed, and rewrites the most opened bills before
their shared copy expires, so readers of these bills never wait for the AI.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from .. import db
from . import analysis_cache, bill_views, new_bills
from .ai_client import AIError
from .bill_sources import fetch_bill_text
from .explain import breakdown
from .sanitize import sanitize_bill_text

log = logging.getLogger(__name__)

MAX_BILLS = 12  # a small share of the free Gemini daily limit, leaving the rest for readers
MAX_FLOOR = 6  # floor bills checked each day, before the most opened ones
BUDGET_S = 240  # stays under the 300 second function limit on Vercel
FRESH_FOR = timedelta(days=2)  # a breakdown with more life left than this is skipped
MIN_GAP_S = 20 * 3600  # the job does nothing if called again sooner, by anyone


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def claim_run() -> bool:
    """True once per MIN_GAP_S, so repeated calls cannot spend the AI quota."""
    now = int(time.time())
    row = await db.query_one("SELECT value FROM counters WHERE name = 'prewarm_last'")
    if row and now - row["value"] < MIN_GAP_S:
        return False
    await db.execute(
        "INSERT INTO counters (name, value) VALUES ('prewarm_last', ?) "
        "ON CONFLICT(name) DO UPDATE SET value = excluded.value",
        (now,),
    )
    return True


async def _due(state: str, bill_no: str) -> bool:
    row = await db.query_one(
        "SELECT MAX(expires_at) AS expires_at FROM bill_analyses WHERE state = ? AND bill_no = ?",
        (state, bill_no),
    )
    expires = row and row["expires_at"]
    return not expires or expires < (_now() + FRESH_FOR).isoformat()


async def _current(state: str, bill_no: str, text_hash: str) -> bool:
    """A breakdown of this exact text exists with more than FRESH_FOR left."""
    row = await db.query_one(
        "SELECT expires_at FROM bill_analyses WHERE state = ? AND bill_no = ? AND text_hash = ?",
        (state, bill_no, text_hash),
    )
    return bool(row) and row["expires_at"] >= (_now() + FRESH_FOR).isoformat()


async def _refresh(state: str, bill_no: str) -> str:
    fetched = await fetch_bill_text(state, bill_no)
    if not fetched.text:
        return "no_text"
    text_hash = analysis_cache.hash_text(fetched.text)
    if await _current(state, bill_no, text_hash):
        return "current"
    title, sections = await breakdown(sanitize_bill_text(fetched.text), f"{state} {bill_no}")
    await analysis_cache.save(state, bill_no, text_hash, title, fetched.source_url, sections, fetched.source)
    return "refreshed"


async def _candidates() -> list[tuple[str, str, bool]]:
    """Bills on the floor first, whose text changes as they move, then the most opened ones."""
    try:
        floor = await new_bills.on_floor(MAX_FLOOR)
    except Exception as exc:  # noqa: BLE001 - the popular bills still get refreshed
        log.error("floor list failed: %s", type(exc).__name__)
        floor = []
    out = [("US", bill_no, True) for bill_no in floor]
    out += [(b["state"], b["bill_no"], False) for b in await bill_views.popular(MAX_BILLS * 3)]
    seen, unique = set(), []
    for state, bill_no, floor_bill in out:
        if (state, bill_no) not in seen:
            seen.add((state, bill_no))
            unique.append((state, bill_no, floor_bill))
    return unique


async def run() -> list[dict]:
    start = time.monotonic()
    done, results = 0, []
    for state, bill_no, floor_bill in await _candidates():
        if done >= MAX_BILLS or time.monotonic() - start > BUDGET_S:
            break
        # A popular bill is only checked near its expiry; a floor bill is checked for a new version every day.
        if not floor_bill and not await _due(state, bill_no):
            continue
        try:
            status = await _refresh(state, bill_no)
        except AIError as exc:
            log.error("prewarm %s %s failed: %s", state, bill_no, exc.code)
            results.append({"bill": f"{state} {bill_no}", "status": exc.code})
            if exc.code == "RATE_LIMIT":
                break
            continue
        except Exception as exc:  # noqa: BLE001 - one bad bill must not stop the rest
            log.error("prewarm %s %s failed: %s", state, bill_no, type(exc).__name__)
            status = type(exc).__name__
        done += status == "refreshed"
        results.append({"bill": f"{state} {bill_no}", "status": status})
    return results
