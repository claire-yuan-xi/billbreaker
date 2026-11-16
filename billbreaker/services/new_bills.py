"""
Keeps a list of the newest federal bills, refreshed by the daily job: every bill
GovInfo printed lately with its title, so a search by name finds bills too new
for Wikipedia, and which of them are on the House or Senate floor now, so their
breakdowns are written before anyone asks.
"""

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx

from .. import db
from ..validation import with_congress
from .bill_sources import current_congress
from .govinfo import UA
from .text import strip_html

log = logging.getLogger(__name__)

BILLS_FEED = "https://www.govinfo.gov/rss/bills.xml"
HOUSE_FLOOR = "https://docs.house.gov/floor/"
KEEP = timedelta(days=120)
# GovInfo's feed also reprints old bills; only versions this recent count as floor action now.
FLOOR_FOR = timedelta(days=14)
ITEM = re.compile(r"<item>([\s\S]*?)</item>", re.I)
PACKAGE = re.compile(r"BILLS-(\d{2,3})(hr|s|hjres|sjres|hconres|sconres)(\d{1,5})([a-z]+)\b", re.I)
PREFIX = {"hr": "HR", "s": "S", "hjres": "HJRES", "sjres": "SJRES", "hconres": "HCONRES", "sconres": "SCONRES"}
# Printed versions that mean a bill was reported, placed on a calendar, passed a chamber or sent to the President.
FLOOR_VERSIONS = {"rh", "rs", "rfs", "rfh", "pcs", "pch", "eh", "es", "eah", "eas", "ath", "ats", "enr", "cph", "cps"}
# The House floor page lists bills this week as "H.R. 7254"; resolutions that only set rules are left out.
HOUSE_ITEM = re.compile(r"\b(H\.\s?R\.|S\.|H\.\s?J\.\s?Res\.|S\.\s?J\.\s?Res\.|H\.\s?Con\.\s?Res\.|S\.\s?Con\.\s?Res\.)\s?(\d{1,5})\b")


def _tag(item: str, name: str) -> str:
    m = re.search(rf"<{name}[^>]*>([\s\S]*?)</{name}>", item, re.I)
    value = m.group(1) if m else ""
    value = re.sub(r"^<!\[CDATA\[|\]\]>$", "", value.strip())
    return html.unescape(html.unescape(value)).replace("\xa0", " ").strip()


def _bill_no(congress: int, prefix: str, number: str) -> str:
    return with_congress(f"{prefix} {int(number)}", None if congress == current_congress() else congress)


def parse_feed(xml: str) -> list[dict]:
    """GovInfo's newest printed bills: number, title, version and when it was printed."""
    rows = []
    for item in ITEM.findall(xml):
        m = PACKAGE.search(_tag(item, "guid") or _tag(item, "link"))
        if not m:
            continue
        congress, kind, number, version = int(m.group(1)), m.group(2).lower(), m.group(3), m.group(4).lower()
        title = re.sub(r"^.*?\(\s*[A-Z]+\s*\)\s*-\s*", "", _tag(item, "title")).strip()
        try:
            published = parsedate_to_datetime(_tag(item, "pubDate")).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            published = datetime.now(timezone.utc).isoformat()
        if title:
            rows.append({
                "bill_no": _bill_no(congress, PREFIX[kind], number),
                "title": title[:300],
                "version": version,
                "published": published,
                "on_floor": version in FLOOR_VERSIONS,
            })
    return rows


def parse_house_floor(page: str) -> list[str]:
    """Bill numbers on the House floor schedule for this week."""
    found = []
    for prefix, number in HOUSE_ITEM.findall(strip_html(page)):
        found.append(_bill_no(current_congress(), re.sub(r"[.\s]", "", prefix).upper(), number))
    return list(dict.fromkeys(found))


async def _get(client: httpx.AsyncClient, url: str, timeout: float) -> str:
    try:
        res = await client.get(url, timeout=timeout, headers={"User-Agent": UA})
        return res.text if res.status_code == 200 else ""
    except httpx.HTTPError:
        return ""


async def read_sources(timeout: float = 15) -> tuple[list[dict], list[str]]:
    """GovInfo's newest printed bills and the House floor schedule, read live."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        feed = parse_feed(await _get(client, BILLS_FEED, timeout))
        house = parse_house_floor(await _get(client, HOUSE_FLOOR, timeout))
    return feed, house


async def refresh(timeout: float = 15) -> dict:
    """Reads both sources and stores what they list; returns how many of each it saw."""
    feed, house = await read_sources(timeout)
    if not feed and not house:
        return {"printed": 0, "house_floor": 0}  # both sources down: keep yesterday's list
    # The newest version of each bill decides its row.
    newest: dict[str, dict] = {}
    for row in sorted(feed, key=lambda r: r["published"]):
        newest[row["bill_no"]] = {**row, "on_floor": row["on_floor"] or row["bill_no"] in house}
    now = datetime.now(timezone.utc).isoformat()
    for bill_no in house:
        newest.setdefault(bill_no, {"bill_no": bill_no, "title": "", "version": "", "published": now, "on_floor": True})
    await db.execute("UPDATE new_bills SET on_floor = 0")
    await db.batch(
        "INSERT INTO new_bills (bill_no, title, version, published, on_floor) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(bill_no) DO UPDATE SET "
        "title = CASE WHEN excluded.title = '' THEN new_bills.title ELSE excluded.title END, "
        "version = CASE WHEN excluded.version = '' THEN new_bills.version ELSE excluded.version END, "
        "published = MAX(new_bills.published, excluded.published), on_floor = excluded.on_floor",
        [(r["bill_no"], r["title"], r["version"], r["published"], int(r["on_floor"])) for r in newest.values()],
    )
    await db.execute("DELETE FROM new_bills WHERE published < ? AND on_floor = 0", ((datetime.now(timezone.utc) - KEEP).isoformat(),))
    return {"printed": len(feed), "house_floor": len(house)}


async def on_floor(limit: int) -> list[str]:
    """Bills on the floor or just passed, newest first."""
    since = (datetime.now(timezone.utc) - FLOOR_FOR).isoformat()
    rows = await db.query(
        "SELECT bill_no FROM new_bills WHERE on_floor = 1 AND published > ? ORDER BY published DESC LIMIT ?",
        (since, limit),
    )
    return [r["bill_no"] for r in rows]


async def titled(limit: int = 400) -> list[dict]:
    """The newest bills with their titles, for a search by name."""
    return await db.query(
        "SELECT bill_no, title FROM new_bills WHERE title != '' ORDER BY published DESC LIMIT ?", (limit,)
    )
