"""
Reads what a person typed in the search box: "MI 1245", "Michigan SB 1245",
"house bill 12", "H.R. 1", "1245" or a bill's name. Pure text work, no network;
services/bill_find.py fills in what is missing.
"""

import re
from dataclasses import dataclass

from ..states import STATE_NAMES
from ..validation import US_STATES, normalize_bill_no, with_congress
from .bill_sources import current_congress

FEDERAL = {"HR", "S", "HRES", "HJRES", "HCONRES", "SRES", "SJRES", "SCONRES"}
# State-style prefixes people use for federal bills.
TO_FEDERAL = {"HB": "HR", "H": "HR", "SB": "S", "HJR": "HJRES", "SJR": "SJRES", "HCR": "HCONRES", "SCR": "SCONRES"}
CHAMBER_WORDS = [
    ("HOUSE JOINT RESOLUTION", "HJR"),
    ("SENATE JOINT RESOLUTION", "SJR"),
    ("HOUSE CONCURRENT RESOLUTION", "HCR"),
    ("SENATE CONCURRENT RESOLUTION", "SCR"),
    ("HOUSE RESOLUTION", "HR"),
    ("SENATE RESOLUTION", "SR"),
    ("HOUSE BILL", "HB"),
    ("SENATE BILL", "SB"),
    ("ASSEMBLY BILL", "AB"),
    ("HOUSE FILE", "HF"),
    ("SENATE FILE", "SF"),
    ("LEGISLATIVE BILL", "LB"),
    ("LEGISLATIVE DOCUMENT", "LD"),
    ("HOUSE", "HB"),
    ("SENATE", "SB"),
    ("ASSEMBLY", "AB"),
]
FEDERAL_LEAD = re.compile(r"^(?:U\.?S\.?A?|FEDERAL|CONGRESS|UNITED STATES)(?=\s)\s*")
FEDERAL_TAIL = re.compile(r"\s+(?:FEDERAL|CONGRESS)$")
NAMES = sorted(((name.upper(), code) for code, name in STATE_NAMES.items() if code != "US"), key=lambda n: -len(n[0]))
FILLER = re.compile(r"\b(?:BILL|STATE|NO|NUMBER|NUM)\b\.?|#")
YEAR = re.compile(r"\b(?:19|20)\d\d\b")
NUMBER_ONLY = re.compile(r"0*(\d{1,6})([A-Z]?)")
CONGRESS = re.compile(r"\b(\d{2,3})(?:ST|ND|RD|TH)\b(?:\s+CONGRESS\b)?")


@dataclass
class Query:
    state: str
    bill_no: str = ""  # "HB 12" when the chamber is known
    number: str = ""  # "1245" when only a number was typed
    words: str = ""  # the text, when it names a bill instead of numbering it
    congress: int | None = None  # "117th Congress", for an older federal bill


def _take_state(text: str, state: str) -> tuple[str, str]:
    """A state's name or two-letter code at either end of the text wins over the picker."""
    for pattern in (FEDERAL_LEAD, FEDERAL_TAIL):
        if m := pattern.search(text):
            return "US", (text[: m.start()] + " " + text[m.end() :]).strip()
    for name, code in NAMES:
        if text.startswith(name + " "):
            return code, text[len(name) :].strip()
        if text.endswith(" " + name):
            return code, text[: -len(name)].strip()
    ends = []
    if m := re.match(r"^([A-Z]{2})[\s.\-]+(.*\d.*)$", text):
        ends.append((m.group(1), m.group(2)))
    if m := re.match(r"^(.*\d.*?)\s+([A-Z]{2})$", text):
        ends.append((m.group(2), m.group(1)))
    for code, rest in ends:
        if code not in US_STATES or code == "US":
            continue
        # "MI 1245" from the federal picker, "MI SB 1245", or the picked state repeated.
        # From another state's picker, "AR 5" is that state's own AR prefix, so it stays.
        if code == state or state == "US" or re.match(r"^[A-Z]", rest):
            return code, rest.strip()
    return state, text


def parse_query(state: str, raw: str) -> Query:
    state = state.upper() if state.upper() in US_STATES else "US"
    text = " ".join(re.sub(r"[,;:()\[\]]", " ", raw.upper()).split())
    if not text:
        return Query(state)
    congress = None
    if m := CONGRESS.search(text):
        text = " ".join((text[: m.start()] + " " + text[m.end() :]).split())
        # "89th" alone from a state's picker is that state's session, not a Congress.
        if "CONGRESS" in m.group(0) or state == "US":
            congress, state = int(m.group(1)), "US"
    state, text = _take_state(text, state)
    if congress and (state != "US" or congress == current_congress()):
        congress = None
    for words, prefix in CHAMBER_WORDS:
        text = re.sub(rf"\b{words}\b", prefix, text)
    core = " ".join(FILLER.sub(" ", text).split())
    if re.search(r"\d", YEAR.sub("", core)):
        core = " ".join(YEAR.sub(" ", core).split())
    if m := NUMBER_ONLY.fullmatch(core.replace(" ", "")):
        return Query(state, number=f"{int(m.group(1))}{m.group(2)}", congress=congress)
    bill_no = normalize_bill_no(core) if re.search(r"\d", core) and len(core) <= 24 else None
    if bill_no:
        prefix, rest = bill_no.split(" ", 1)
        if state == "US":
            prefix = TO_FEDERAL.get(prefix, prefix)
        return Query(state, bill_no=with_congress(f"{prefix} {rest}", congress), congress=congress)
    return Query(state, words=" ".join(raw.split())[:120], congress=congress)
