"""All-time totals for the stats page."""

from . import counts

# Counted before the production database was replaced on 2026-11-01. Those rows
# are gone, so the last reading is carried forward here.
BASELINE = {"visits": 173, "clicks": 0}
NAMES = ("visits", "clicks")
DAYS = 14


async def summary() -> dict:
    now = {name: await counts.total(name) for name in NAMES}
    days = await counts.by_day(DAYS)
    return {
        "totals": {name: BASELINE[name] + now[name] for name in NAMES},
        "today": next(iter(days.values())),
        "days": [{"day": day, **{n: values.get(n, 0) for n in NAMES}} for day, values in days.items()],
    }
