"""Function-calling schemas for each section of the AI breakdown."""


def _obj(properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required or list(properties),
        "additionalProperties": False,
    }


def _list_of(properties: dict) -> dict:
    return {"type": "array", "items": _obj(properties)}


STRING = {"type": "string"}

QUICK_TAKE = {
    "name": "quick_take",
    "description": "Plain-English quick take on a bill.",
    "parameters": _obj(
        {
            "tldr": STRING,
            "controversy_score": {"type": "integer", "minimum": 0, "maximum": 10},
            "controversy_reason": STRING,
            "dollar_impact": STRING,
            "timeline": STRING,
        }
    ),
}

WINNERS_LOSERS = {
    "name": "winners_losers",
    "description": "Who benefits and who loses under this bill.",
    "parameters": _obj(
        {
            "winners": _list_of({"group": STRING, "why": STRING}),
            "losers": _list_of({"group": STRING, "why": STRING}),
        }
    ),
}

CITATIONS = {
    "name": "citations",
    "description": "Direct quotes from the bill that ground the analysis.",
    "parameters": _obj(
        {"citations": _list_of({"quote": STRING, "section": STRING, "why_matters": STRING})}
    ),
}

SUPPORTERS_CRITICS = {
    "name": "supporters_vs_critics",
    "description": "Steel-manned arguments from both sides.",
    "parameters": _obj(
        {
            "supporters": _list_of({"point": STRING, "who": STRING}),
            "critics": _list_of({"point": STRING, "who": STRING}),
        }
    ),
}

STATUS_QUO = {
    "name": "status_quo_diff",
    "description": "How this changes current law in plain English.",
    "parameters": _obj(
        {
            "changes": _list_of(
                {
                    "today": STRING,
                    "after": STRING,
                    "magnitude": {"type": "string", "enum": ["minor", "moderate", "major"]},
                }
            )
        }
    ),
}

FOR_YOU = {
    "name": "for_you",
    "description": "How the bill could touch one reader, from their own answers.",
    "parameters": _obj(
        {
            "summary": STRING,
            "points": _list_of({"topic": STRING, "effect": STRING}),
        }
    ),
}
