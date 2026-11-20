"""Stripe Checkout for one-time donations. Checkout shows Apple Pay, Google Pay and card on its own."""

import re

import httpx

from ..config import settings

AMOUNTS = (1, 2, 5, 10)
CHECKOUT_URL = "https://api.stripe.com/v1/checkout/sessions"


class DonateError(Exception):
    pass


def enabled() -> bool:
    return bool(settings.stripe_secret_key)


async def checkout_url(dollars: int, site: str) -> str:
    """Creates a Checkout session for a fixed amount and returns its hosted page."""
    if dollars not in AMOUNTS:
        raise DonateError("Pick an amount")
    if not enabled():
        raise DonateError("Donations are not open yet")
    form = {
        "mode": "payment",
        "submit_type": "donate",
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": str(dollars * 100),
        "line_items[0][price_data][product_data][name]": "BillBreaker donation",
        "success_url": f"{site}/donate?thanks=1",
        "cancel_url": f"{site}/donate",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(CHECKOUT_URL, data=form, auth=(settings.stripe_secret_key, ""))
    body = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
    url = body.get("url") if res.is_success else None
    if not url:
        # Stripe's own reason (never the key), so the status check shows what to fix.
        reason = (body.get("error") or {}).get("message") or f"HTTP {res.status_code}"
        reason = re.sub(r"\b[sr]k_\w*\**\w*", "[key]", reason)[:300]
        raise DonateError(f"Payment page did not open: {reason}")
    return url
