"""HTML pages."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from .ml import notebook_run as run
from .ml.claims_check import FLAG_LABELS, SERIOUS, check_claims, serious_count
from .ml.profile_terms import clean_profile, profile_terms
from .services import shares
from .services.render import render_share
from .templating import templates
from .validation import SLUG

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.get("/bill", response_class=HTMLResponse)
async def bill(request: Request, state: str = "US", number: str = ""):
    return templates.TemplateResponse(request, "bill.html", {"state": state, "number": number})


@router.get("/b/{slug}", response_class=HTMLResponse)
async def shared(request: Request, slug: str):
    row = await shares.get(slug) if SLUG.match(slug) else None
    if not row:
        return templates.TemplateResponse(request, "share_missing.html", status_code=404)
    context = {"row": row, "sections": render_share(row["payload"])}
    return templates.TemplateResponse(request, "share.html", context)


@router.get("/admin/ml", response_class=HTMLResponse)
async def admin_ml(request: Request):
    report = check_claims(
        run.EXAMPLE_RUN["personalized"],
        [run.EXAMPLE_RUN["general"], *(s["heading"] for s in run.EXAMPLE_RUN["sections"])],
        " ".join(run.EXAMPLE_PROFILE.values()),
    )
    base, tuned = run.ROUGE
    context = {
        "card": run.MODEL_CARD,
        "rouge": run.ROUGE,
        "lift": round((tuned["rouge1"] / base["rouge1"] - 1) * 100),
        "samples": run.SAMPLES,
        "example": run.EXAMPLE_RUN,
        "example_profile": clean_profile(run.EXAMPLE_PROFILE),
        "example_terms": profile_terms(run.EXAMPLE_PROFILE),
        "report": report,
        "serious": serious_count(report),
        "flag_labels": FLAG_LABELS,
        "serious_flags": SERIOUS,
        "example_profile_raw": run.EXAMPLE_PROFILE,
    }
    return templates.TemplateResponse(request, "admin/ml.html", context)


@router.get("/admin/abuse", response_class=HTMLResponse)
async def admin_abuse(request: Request):
    return templates.TemplateResponse(request, "admin/abuse.html")
