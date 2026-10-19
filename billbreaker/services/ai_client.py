"""
Calls Gemini through its OpenAI-compatible endpoint with a forced function call.
When the main model is out of free quota, missing or overloaded, it tries the
fallback model, and waits once for a short rate-limit window.
"""

import asyncio
import json
import logging
import re

import httpx

from ..config import settings

log = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
TRY_NEXT_MODEL = {404, 429, 500, 503}
MAX_WAIT = 20
_transport: httpx.AsyncBaseTransport | None = None  # tests swap in a fake Gemini


class AIError(Exception):
    """code is AI_NO_KEY, AI_BAD_KEY, AI_FORBIDDEN, RATE_LIMIT, AI_TIMEOUT or AI_GATEWAY_ERROR."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _models() -> list[str]:
    models = [settings.gemini_model, settings.gemini_fallback_model]
    return [m for i, m in enumerate(models) if m and m not in models[:i]]


def _retry_after(body: str) -> int | None:
    match = re.search(r'"retryDelay"\s*:\s*"(\d+)(?:\.\d+)?s"', body)
    return int(match.group(1)) if match else None


async def _send(client: httpx.AsyncClient, model: str, system: str, user: str, schema: dict) -> httpx.Response:
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "tools": [{"type": "function", "function": schema}],
        "tool_choice": {"type": "function", "function": {"name": schema["name"]}},
    }
    try:
        return await client.post(
            GEMINI_URL, json=body, headers={"Authorization": f"Bearer {settings.gemini_api_key}"}
        )
    except httpx.TimeoutException as exc:
        log.error("Gemini %s timed out", model)
        raise AIError("AI_TIMEOUT") from exc
    except httpx.HTTPError as exc:
        log.error("Gemini request failed: %s", exc)
        raise AIError("AI_GATEWAY_ERROR") from exc


def _result(res: httpx.Response, model: str) -> dict:
    if res.status_code != 200:
        log.error("Gemini %s on %s: %s", res.status_code, model, res.text[:500])
    if res.status_code == 429:
        raise AIError("RATE_LIMIT")
    if res.status_code == 403:
        raise AIError("AI_FORBIDDEN")
    if res.status_code in (400, 401) and "API key" in res.text:
        raise AIError("AI_BAD_KEY")
    if res.status_code != 200:
        raise AIError("AI_GATEWAY_ERROR")
    try:
        call = res.json()["choices"][0]["message"]["tool_calls"][0]
        return json.loads(call["function"]["arguments"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        log.error("Gemini %s returned no function call: %s", model, res.text[:500])
        raise AIError("AI_GATEWAY_ERROR") from exc


async def call_ai(system: str, user: str, schema: dict) -> dict:
    if not settings.gemini_api_key:
        raise AIError("AI_NO_KEY")
    models = _models()
    async with httpx.AsyncClient(timeout=120, transport=_transport) as client:
        for i, model in enumerate(models):
            res = await _send(client, model, system, user, schema)
            last = i == len(models) - 1
            if res.status_code in TRY_NEXT_MODEL and not last:
                log.warning("Gemini %s on %s, trying %s", res.status_code, model, models[i + 1])
                continue
            wait = _retry_after(res.text) if res.status_code == 429 else None
            if wait is not None and wait <= MAX_WAIT:
                await asyncio.sleep(wait + 1)
                res = await _send(client, model, system, user, schema)
            return _result(res, model)
    raise AIError("AI_GATEWAY_ERROR")
