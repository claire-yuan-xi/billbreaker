"""Small text helpers shared by the bill fetchers and the feed parser."""

import re

_ENTITIES = {
    "&nbsp;": " ",
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
}


def decode_entities(s: str) -> str:
    for k, v in _ENTITIES.items():
        s = s.replace(k, v)
    return s


def strip_html(html: str, keep_breaks: bool = True) -> str:
    s = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.I)
    if keep_breaks:
        s = re.sub(r"</?(p|br|div|li|h\d|tr|td)[^>]*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    if keep_breaks:
        s = decode_entities(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def extract_tag(tag: str, xml: str) -> str:
    m = re.search(rf"<{tag}>([\s\S]*?)</{tag}>", xml)
    if not m:
        return ""
    return re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1)).strip()


def clean_title(title: str) -> str:
    """Drops the trailing ' - Publisher' from a feed headline."""
    return re.sub(r" - [^-]+$", "", title)
