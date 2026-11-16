"""Stripe Checkout for one-time donations. Checkout shows Apple Pay, Google Pay and card on its own."""

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
    url = res.json().get("url") if res.is_success else None
    if not url:
        raise DonateError("Payment page did not open")
    return url
