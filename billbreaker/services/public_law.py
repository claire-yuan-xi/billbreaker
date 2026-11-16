"""
Finds the bill behind an enacted law's number, like Public Law 117-169. GovInfo's
copy of the law names the bill it came from: "[H.R. 5376]".
"""

import re

import httpx

from .govinfo import read_head

# The bill a law came from, as the law's own header writes it.
ORIGIN = re.compile(r"\[\s*(H\.\s?R\.|S\.|H\.\s?J\.\s?Res\.|S\.\s?J\.\s?Res\.)\s?(\d{1,5})\s*\]", re.I)


async def law_bill(client: httpx.AsyncClient, congress: int, number: int, timeout: float):
    """(congress, prefix, number, start of the law's text), or None when GovInfo has no such law."""
    url = f"https://www.govinfo.gov/link/plaw/{congress}/public/{number}?link-type=html"
    text = await read_head(client, url, "PLAW-", timeout)
    m = ORIGIN.search(text or "")
    if not m:
        return None
    prefix = re.sub(r"[.\s]", "", m.group(1)).upper()
    return congress, prefix, m.group(2), text
