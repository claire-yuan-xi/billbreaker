"""
Turns the model's general summary into an explanation for one reader. The summary
comes from the fine-tuned FLAN-T5 running in the admin's browser; Gemini only
rewrites it for the reader, using the summary and the bill's top-ranked sections.
"""

from ..services.ai_client import call_ai
from ..services.ai_schemas import STRING, _obj

SCHEMA = {
    "name": "personalized_explanation",
    "description": "The bill explained for this reader.",
    "parameters": _obj({"personalized": STRING}),
}

SYSTEM = (
    "You explain US bills to one reader in plain English. Use only facts from the "
    "summary and sections you are given; never add numbers, dates or programs that "
    "are not in them. Say how the bill could touch this reader's life, in four to six "
    "short sentences. No markdown, no em dashes."
)


def _prompt(general: str, sections: list[dict], profile: dict) -> str:
    reader = "\n".join(f"- {k}: {v}" for k, v in profile.items() if v) or "- (no answers)"
    top = "\n\n".join(f"{s['heading']}\n{s['body'][:1500]}" for s in sections[:3])
    return f"Reader:\n{reader}\n\nSummary:\n{general}\n\nMost relevant sections:\n{top}"


async def personalize(general: str, sections: list[dict], profile: dict) -> str:
    data = await call_ai(SYSTEM, _prompt(general, sections, profile), SCHEMA)
    return str(data.get("personalized", "")).strip()
