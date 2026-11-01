"""
Nightly refresh: rewrites the breakdowns of the most opened bills before their
shared copy expires, so readers of popular bills never wait for the AI.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from .. import db
from . import analysis_cache, bill_views
from .ai_client import AIError
from .bill_sources import fetch_bill_text
from .explain import breakdown
from .sanitize import sanitize_bill_text

log = logging.getLogger(__name__)

MAX_BILLS = 8  # a small share of the free Gemini daily limit, leaving the rest for readers
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


async def _refresh(state: str, bill_no: str) -> str:
    fetched = await fetch_bill_text(state, bill_no)
    if not fetched.text:
        return "no_text"
    title, sections = await breakdown(sanitize_bill_text(fetched.text), f"{state} {bill_no}")
    await analysis_cache.save(
        state, bill_no, analysis_cache.hash_text(fetched.text), title, fetched.source_url, sections
    )
    return "refreshed"


async def run() -> list[dict]:
    start = time.monotonic()
    done, results = 0, []
    for bill in await bill_views.popular(MAX_BILLS * 3):
        if done >= MAX_BILLS or time.monotonic() - start > BUDGET_S:
            break
        state, bill_no = bill["state"], bill["bill_no"]
        if not await _due(state, bill_no):
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
