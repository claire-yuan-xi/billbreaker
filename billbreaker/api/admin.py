"""Admin endpoints: abuse events (token-gated) and the model playground."""

import hmac

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..ml.claims_check import FLAG_LABELS, SERIOUS, check_claims, serious_count
from ..ml.personalize import personalize
from ..ml.profile_terms import clean_profile
from ..ml.sections import rank_sections
from ..services import abuse
from ..services.ai_client import AIError
from ..templating import templates

router = APIRouter(prefix="/api/admin")


class AbuseIn(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    limit: int = Field(default=100, ge=1, le=500)


@router.post("/abuse-events")
async def abuse_events(data: AbuseIn):
    expected = settings.abuse_admin_token
    if not expected:
        return {"ok": False, "error": "ABUSE_ADMIN_TOKEN not configured on the server."}
    if not hmac.compare_digest(data.token.encode(), expected.encode()):
        return {"ok": False, "error": "Invalid token."}
    return {"ok": True, "events": await abuse.recent_events(data.limit)}


class RankIn(BaseModel):
    text: str = Field(default="", max_length=200_000)
    profile: dict[str, str] = {}


def _partial(name: str, **context) -> str:
    return templates.get_template(f"admin/{name}.html").render(**context)


@router.post("/ml/rank")
async def rank(data: RankIn):
    ranking = rank_sections(data.text, data.profile)
    terms_html = _partial("_reader_terms", profile=clean_profile(data.profile), terms=ranking["terms"])
    table_html = _partial("_section_table", rows=ranking["ranked"], total=ranking["total"]) if data.text.strip() else ""
    return {**ranking, "termsHtml": terms_html, "tableHtml": table_html}


class GenerateIn(RankIn):
    general: str = Field(min_length=1, max_length=5_000)


@router.post("/ml/generate")
async def generate(data: GenerateIn):
    ranking = rank_sections(data.text, data.profile)
    try:
        personalized = await personalize(data.general, ranking["ranked"], data.profile)
    except AIError as exc:
        raise HTTPException(502, f"Personalizing failed ({exc.code}).") from exc
    sources = [data.general, *(f"{s['heading']} {s['body']}" for s in ranking["ranked"])]
    report = check_claims(personalized, sources, " ".join(data.profile.values()))
    html = _partial(
        "_generated",
        general=data.general,
        report=report,
        serious=serious_count(report),
        flag_labels=FLAG_LABELS,
        serious_flags=SERIOUS,
    )
    return {"general": data.general, "personalized": personalized, "report": report, "html": html}
