"""Input patterns shared by the API and the page routes."""

import re

BILL_NO = re.compile(r"^[A-Za-z]{1,8}[.\s-]?\d{1,6}[A-Za-z]?$")
# Accepts how people type bill numbers: "HB 12", "H.B. 12", "hb12", "S-5", "A1234B".
LOOSE_BILL_NO = re.compile(r"^\s*([A-Za-z][A-Za-z.\s]{0,15}?)[\s.-]*(\d{1,6})([A-Za-z]?)\s*$")
# A federal bill from an older Congress carries it: "HR 5376 (117th)".
CONGRESS_SUFFIX = re.compile(r"^(.*?)\s*\((\d{1,3})(?:st|nd|rd|th)?\)\s*$", re.I)
STATE = re.compile(r"^[A-Z]{2,4}$")
DEVICE_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
SLUG = re.compile(r"^[a-z0-9]{4,16}$")

US_STATES = frozenset(
    "US AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH "
    "NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
)


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def split_congress(bill_no: str) -> tuple[str, int | None]:
    """"HR 5376 (117th)" becomes ("HR 5376", 117)."""
    m = CONGRESS_SUFFIX.match(bill_no)
    if m and 1 <= int(m.group(2)) <= 200:
        return m.group(1), int(m.group(2))
    return bill_no, None


def with_congress(bill_no: str, congress: int | None) -> str:
    return f"{bill_no} ({ordinal(congress)})" if congress else bill_no


def normalize_bill_no(raw: str) -> str | None:
    """"H.B. 12" becomes "HB 12"; returns None when it is not a bill number."""
    base, congress = split_congress(raw)
    m = LOOSE_BILL_NO.match(base)
    if not m:
        return None
    letters = re.sub(r"[^A-Za-z]", "", m.group(1)).upper()
    if not 1 <= len(letters) <= 8:
        return None
    return with_congress(f"{letters} {m.group(2)}{m.group(3).upper()}", congress)
