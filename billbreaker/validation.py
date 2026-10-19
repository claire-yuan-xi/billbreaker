"""Input patterns shared by the API and the page routes."""

import re

BILL_NO = re.compile(r"^[A-Za-z]{1,8}[.\s-]?\d{1,6}$")
STATE = re.compile(r"^[A-Z]{2,4}$")
DEVICE_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
SLUG = re.compile(r"^[a-z0-9]{4,16}$")

US_STATES = frozenset(
    "US AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH "
    "NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
)
