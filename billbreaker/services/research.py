"""
When a bill's text cannot be fetched (most state bills, and federal bills when the
official sites refuse the host), Gemini looks the bill up with Google Search and
writes the same breakdown from what it finds, along with the pages it used.
"""

import json
import re

from .ai_client import AIError, call_with_search
from .explain import BASE_SYSTEM, BREAKDOWN, SECTIONS
from .render import ORDER

NOT_FOUND = "NOT_FOUND"


def _skeleton(schema: dict):
    """An example value for a JSON schema, used to show Gemini the exact shape."""
    kind = schema.get("type")
    if kind == "object":
        return {k: _skeleton(v) for k, v in schema.get("properties", {}).items()}
    if kind == "array":
        return [_skeleton(schema.get("items", {}))]
    if "enum" in schema:
        return "|".join(schema["enum"])
    return 0 if kind == "integer" else "..."


SHAPE = json.dumps(_skeleton(BREAKDOWN["parameters"]), indent=1)
FIELDS = "\n".join(f"- {name}: {text}" for name, (_, text) in SECTIONS.items())


def _prompt(jurisdiction: str, bill_no: str) -> str:
    return (
        f"Find {jurisdiction} bill {bill_no} with Google Search, preferring the official legislature "
        "site, and explain the most recent session's version of it.\n"
        f"If you cannot find this exact bill, reply with only the word {NOT_FOUND}.\n"
        "Otherwise reply with only a JSON object of exactly this shape, no markdown:\n"
        f"{SHAPE}\n\nFill in every field.\n- title: a short plain-English title for this bill.\n{FIELDS}\n"
        "For citations, quote only text you actually found from the bill; if you found none, return an "
        "empty list."
    )


def _json(text: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise AIError("AI_GATEWAY_ERROR")
    try:
        data = json.loads(match.group(0))
    except ValueError as exc:
        raise AIError("AI_GATEWAY_ERROR") from exc
    if not isinstance(data, dict):
        raise AIError("AI_GATEWAY_ERROR")
    return data


async def research_breakdown(jurisdiction: str, bill_no: str, fallback_title: str):
    """Returns (title, sections, pages), or None when the bill could not be found."""
    text, pages = await call_with_search(BASE_SYSTEM, _prompt(jurisdiction, bill_no))
    if NOT_FOUND in text[:40] or "{" not in text:
        return None
    data = _json(text)
    sections = [{"event": e, "data": data[e]} for e in ORDER if isinstance(data.get(e), dict)]
    if not sections:
        return None
    title = data.get("title")
    title = title.strip()[:160] if isinstance(title, str) and title.strip() else fallback_title
    return title, sections, pages
