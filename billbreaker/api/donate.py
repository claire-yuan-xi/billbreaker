"""Donate form: sends the visitor to Stripe Checkout, or back to /donate with an error."""

import logging

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from ..config import settings
from ..services.donate import DonateError, checkout_url
from ..services.rate_limit import bump, client_ip

log = logging.getLogger(__name__)
router = APIRouter()


def _site(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    return f"{proto}://{request.url.netloc}"


@router.post("/donate")
async def donate(request: Request, amount: int = Form(...)):
    if not settings.donations_open:
        raise HTTPException(status_code=404)
    if not (await bump(f"ip:{client_ip(request)}:donate:1h", 20, 3600, endpoint="donate")).allowed:
        return RedirectResponse("/donate?error=busy", status_code=303)
    try:
        url = await checkout_url(amount, _site(request))
    except DonateError as exc:
        log.warning("donate: %s", exc)
        return RedirectResponse("/donate?error=1", status_code=303)
    except Exception:  # noqa: BLE001 - Stripe down or unreachable
        log.exception("donate: checkout failed")
        return RedirectResponse("/donate?error=1", status_code=303)
    return RedirectResponse(url, status_code=303)
