"""Bill page header data and published share pages."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from ..services import shares
from ..services.bill_find import describe, resolve
from ..services.bill_query import parse_query
from ..services.bill_sources import official_search_url
from ..services.rate_limit import bump, client_ip
from ..states import STATE_NAMES
from ..validation import STATE, normalize_bill_no

router = APIRouter()


class MetaIn(BaseModel):
    state: str = "US"
    # What the person typed: a number, a number with its state, or a bill's name.
    billNo: str = Field(default="", max_length=160)
    hasText: bool = False

    @field_validator("state")
    @classmethod
    def _state(cls, v: str) -> str:
        if not STATE.match(v):
            raise ValueError("invalid state")
        return v


@router.post("/api/bill-meta")
async def bill_meta(data: MetaIn, request: Request):
    if not data.billNo.strip():
        return {"id": "pasted bill", "jurisdiction": data.state, "found": False, "textProvided": data.hasText}
    query = parse_query(data.state, data.billNo)
    use_ai = False
    # Lookups spend the free Open States quota and a name search may ask Gemini.
    if not (query.bill_no and query.state == "US"):
        rl = await bump(f"ip:{client_ip(request)}:find", 60, 600, endpoint="find")
        if not rl.allowed:
            raise HTTPException(429, "Too many searches. Try again in a few minutes.")
        use_ai = bool(query.words) and rl.count <= 30
    found = await resolve(data.state, data.billNo, use_ai=use_ai)
    best = found.best
    state = best.state if best else found.query.state
    return {
        **describe(found),
        "id": best.bill_no if best else data.billNo.strip()[:60],
        "jurisdiction": state,
        "place": "United States Federal" if state == "US" else STATE_NAMES.get(state, state),
        "sourceUrl": official_search_url(state, best.bill_no) if best else None,
        "textProvided": data.hasText,
        "notice": None,
    }


class ShareIn(BaseModel):
    state: str = Field(pattern=r"^[A-Z]{2}$")
    bill_no: str = Field(default="", max_length=20)
    title: str | None = Field(default=None, max_length=300)
    source_url: str | None = Field(default=None, max_length=2000)
    payload: dict

    @field_validator("bill_no")
    @classmethod
    def _bill(cls, v: str) -> str:
        if v and not normalize_bill_no(v):
            raise ValueError("invalid bill number")
        return v


@router.post("/api/share")
async def create_share(data: ShareIn, request: Request):
    ip = client_ip(request)
    for key, limit, window, message in (
        ("1m", 5, 60, "Too many publishes from this IP. Wait a minute and try again."),
        ("1h", 30, 3600, "Hourly publish limit reached. Try again later."),
    ):
        if not (await bump(f"ip:{ip}:publish:{key}", limit, window, endpoint="publish")).allowed:
            raise HTTPException(429, message)
    try:
        slug = await shares.create(data.state, data.bill_no, data.title, data.source_url, data.payload)
    except ValueError as exc:
        raise HTTPException(413, str(exc)) from exc
    return {"slug": slug}
