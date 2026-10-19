"""Neutralizes prompt-injection markers so the model treats bill text as data."""

import re

MAX_CHARS = 80_000


def sanitize_bill_text(text: str) -> str:
    out = text.replace("```", "ʼʼʼ")
    out = re.sub(r"</?bill_text>", "", out, flags=re.I)
    out = re.sub(r"^([ \t]*)(system|assistant|user)\s*:", r"\1\2 :", out, flags=re.I | re.M)
    out = re.sub(r"^[ \t]*###+", "", out, flags=re.M)
    return out[:MAX_CHARS]
