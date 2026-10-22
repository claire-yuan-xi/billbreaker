"""Renders each section of an analysis to HTML, for the bill page stream and the share page."""

from ..templating import templates

ORDER = ["quick_take", "status_quo_diff", "winners_losers", "supporters_vs_critics", "citations"]
# Written for one reader, so never cached or shared.
PERSONAL = ["for_you"]

# Shared pages store sections under shorter keys.
SHARE_KEYS = {
    "quick": "quick_take",
    "sq": "status_quo_diff",
    "wl": "winners_losers",
    "sc": "supporters_vs_critics",
    "citations": "citations",
}


def _rows(items, heading: str, sub: str, large: bool):
    return [(i.get(heading, ""), i.get(sub, ""), large) for i in items or [] if isinstance(i, dict)]


def _columns(event: str, data: dict):
    if event == "winners_losers":
        return [
            ("Winners", "#3a7a4a", _rows(data.get("winners"), "group", "why", True), "No clear winners identified."),
            ("Losers", "#a04438", _rows(data.get("losers"), "group", "why", True), "No clear losers identified."),
        ]
    return [
        ("What supporters say", "#3a3a3a", _rows(data.get("supporters"), "point", "who", False), None),
        ("What critics say", "#3a3a3a", _rows(data.get("critics"), "point", "who", False), None),
    ]


def render_section(event: str, data: dict) -> str:
    if event not in ORDER + PERSONAL or not isinstance(data, dict):
        return ""
    if event in ("winners_losers", "supporters_vs_critics"):
        template = templates.get_template("analysis/_two_columns.html")
        return template.render(columns=_columns(event, data))
    return templates.get_template(f"analysis/{event}.html").render(data=data)


def render_share(payload: dict) -> list[str]:
    """The sections of a shared page, in reading order."""
    by_event = {SHARE_KEYS[k]: v for k, v in payload.items() if k in SHARE_KEYS and v}
    return [render_section(e, by_event[e]) for e in ORDER if e in by_event]
