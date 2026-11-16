import asyncio

from billbreaker.services import new_bills
from billbreaker.services.bill_sources import current_congress

NOW = current_congress()


def item(package, title, date="Fri, 13 Nov 2026 06:55:00 +0000"):
    return (
        f'<item><guid isPermaLink="false">{package}</guid><title>{title}</title>'
        f"<pubDate>{date}</pubDate><link>https://www.govinfo.gov/app/details/{package}</link></item>"
    )


FEED = "<rss><channel>" + "".join([
    item(f"BILLS-{NOW}hr11003ih", "H.R.&amp;nbsp;11003&amp;nbsp;(IH) - Abuse of the Pardon Prevention Act of 2026"),
    item(f"BILLS-{NOW}s5712es", "S.&amp;nbsp;5712&amp;nbsp;(ES) - Burn Pits Act"),
    item("BILLS-117hr5376enr", "H.R.&amp;nbsp;5376&amp;nbsp;(ENR) - Inflation Reduction Act of 2022"),
]) + "</channel></rss>"


def test_reads_the_govinfo_feed():
    rows = new_bills.parse_feed(FEED)
    assert [(r["bill_no"], r["title"], r["on_floor"]) for r in rows] == [
        ("HR 11003", "Abuse of the Pardon Prevention Act of 2026", False),
        ("S 5712", "Burn Pits Act", True),
        ("HR 5376 (117th)", "Inflation Reduction Act of 2022", True),
    ]
    assert rows[0]["published"].startswith("2026-11-13")


def test_reads_the_house_floor_page():
    page = "<table><tr><td>H.R. 7254</td><td>A bill</td></tr><tr><td>H.Res. 900</td></tr><tr><td>S. 12</td></tr></table>"
    assert new_bills.parse_house_floor(page) == ["HR 7254", "S 12"]


def test_refresh_stores_titles_and_floor_bills(monkeypatch):
    pages = {new_bills.BILLS_FEED: FEED, new_bills.HOUSE_FLOOR: "<p>H.R. 11003</p>"}

    async def get(client, url, timeout):
        return pages[url]

    monkeypatch.setattr(new_bills, "_get", get)
    assert asyncio.run(new_bills.refresh()) == {"printed": 3, "house_floor": 1}
    floor = set(asyncio.run(new_bills.on_floor(10)))
    assert floor == {"HR 11003", "S 5712", "HR 5376 (117th)"}
    titles = {r["bill_no"]: r["title"] for r in asyncio.run(new_bills.titled())}
    assert titles["HR 11003"] == "Abuse of the Pardon Prevention Act of 2026"


def test_refresh_keeps_the_list_when_both_sources_are_down(monkeypatch):
    async def down(client, url, timeout):
        return ""

    monkeypatch.setattr(new_bills, "_get", down)
    assert asyncio.run(new_bills.refresh()) == {"printed": 0, "house_floor": 0}
