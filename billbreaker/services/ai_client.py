"""
Calls Gemini, either through its OpenAI-compatible endpoint with a forced function
call, or through the native endpoint with Google Search turned on. When the main
model is out of free quota, missing or overloaded, it tries the fallback model,
and waits once for a short rate-limit window.
"""

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable

import httpx

from ..config import settings

log = logging.getLogger(__name__)

OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
NATIVE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TRY_NEXT_MODEL = {404, 429, 500, 503}
MAX_WAIT = 20
_transport: httpx.AsyncBaseTransport | None = None  # tests swap in a fake Gemini

Send = Callable[[httpx.AsyncClient, str], Awaitable[httpx.Response]]


class AIError(Exception):
    """code is AI_NO_KEY, AI_BAD_KEY, AI_FORBIDDEN, RATE_LIMIT, AI_TIMEOUT or AI_GATEWAY_ERROR."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def models() -> list[str]:
    names = [settings.gemini_model, settings.gemini_fallback_model]
    return [m for i, m in enumerate(names) if m and m not in names[:i]]


def error_message(body: str) -> str:
    """Google's own error text, which never contains the key."""
    try:
        data = json.loads(body)
    except ValueError:
        return body[:200]
    if isinstance(data, list) and data:
        data = data[0]
    error = data.get("error") if isinstance(data, dict) else None
    return str((error or {}).get("message", ""))[:300] if isinstance(error, dict) else body[:200]


def _retry_after(body: str) -> int | None:
    match = re.search(r'"retryDelay"\s*:\s*"(\d+)(?:\.\d+)?s"', body)
    return int(match.group(1)) if match else None


async def _post(client: httpx.AsyncClient, url: str, body: dict, model: str) -> httpx.Response:
    # The OpenAI-compatible endpoint takes a bearer token; the native one takes the key header.
    native = url.startswith(NATIVE_URL.split("{")[0])
    key = settings.gemini_api_key
    headers = {"x-goog-api-key": key} if native else {"Authorization": f"Bearer {key}"}
    try:
        return await client.post(url, json=body, headers=headers)
    except httpx.TimeoutException as exc:
        log.error("Gemini %s timed out", model)
        raise AIError("AI_TIMEOUT") from exc
    except httpx.HTTPError as exc:
        log.error("Gemini request failed: %s", exc)
        raise AIError("AI_GATEWAY_ERROR") from exc


def _check(res: httpx.Response, model: str) -> None:
    if res.status_code == 200:
        return
    log.error("Gemini %s on %s: %s", res.status_code, model, error_message(res.text))
    if res.status_code == 429:
        raise AIError("RATE_LIMIT")
    if res.status_code == 403:
        raise AIError("AI_FORBIDDEN")
    if res.status_code in (400, 401) and "API key" in res.text:
        raise AIError("AI_BAD_KEY")
    raise AIError("AI_GATEWAY_ERROR")


async def _run(send: Send) -> tuple[httpx.Response, str]:
    """Sends to each model in turn until one answers; returns that answer and its model."""
    if not settings.gemini_api_key:
        raise AIError("AI_NO_KEY")
    names = models()
    async with httpx.AsyncClient(timeout=120, transport=_transport) as client:
        for i, model in enumerate(names):
            res = await send(client, model)
            if res.status_code in TRY_NEXT_MODEL and i < len(names) - 1:
                log.warning("Gemini %s on %s: %s", res.status_code, model, error_message(res.text))
                continue
            wait = _retry_after(res.text) if res.status_code == 429 else None
            if wait is not None and wait <= MAX_WAIT:
                await asyncio.sleep(wait + 1)
                res = await send(client, model)
            _check(res, model)
            return res, model
    raise AIError("AI_GATEWAY_ERROR")


async def call_ai(system: str, user: str, schema: dict) -> dict:
    """One forced function call; returns its arguments."""

    def send(client: httpx.AsyncClient, model: str):
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "tools": [{"type": "function", "function": schema}],
            "tool_choice": {"type": "function", "function": {"name": schema["name"]}},
        }
        return _post(client, OPENAI_URL, body, model)

    res, model = await _run(send)
    try:
        call = res.json()["choices"][0]["message"]["tool_calls"][0]
        return json.loads(call["function"]["arguments"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        log.error("Gemini %s returned no function call: %s", model, res.text[:500])
        raise AIError("AI_GATEWAY_ERROR") from exc


async def call_with_search(system: str, user: str) -> tuple[str, list[dict]]:
    """A free-text answer written with Google Search; returns the text and the pages used."""

    def send(client: httpx.AsyncClient, model: str):
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "tools": [{"google_search": {}}],
        }
        return _post(client, NATIVE_URL.format(model=model), body, model)

    res, model = await _run(send)
    try:
        candidate = res.json()["candidates"][0]
        parts = candidate["content"]["parts"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        log.error("Gemini %s returned no answer: %s", model, res.text[:500])
        raise AIError("AI_GATEWAY_ERROR") from exc
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    chunks = (candidate.get("groundingMetadata") or {}).get("groundingChunks") or []
    pages = [c["web"] for c in chunks if isinstance(c.get("web"), dict) and c["web"].get("uri")]
    return text, [{"url": p["uri"], "title": p.get("title") or p["uri"]} for p in pages[:5]]


async def probe() -> list[dict]:
    """A tiny request to each model at once, reporting Google's status and message."""
    if not settings.gemini_api_key:
        return [{"model": m, "status": None, "message": "No GEMINI_API_KEY on the server."} for m in models()]

    async def one(client: httpx.AsyncClient, model: str) -> dict:
        body = {"model": model, "messages": [{"role": "user", "content": "Reply with the word ok."}]}
        try:
            res = await _post(client, OPENAI_URL, body, model)
        except AIError as exc:
            return {"model": model, "status": None, "message": exc.code}
        message = "ok" if res.status_code == 200 else error_message(res.text)
        return {"model": model, "status": res.status_code, "message": message}

    async with httpx.AsyncClient(timeout=20, transport=_transport) as client:
        return list(await asyncio.gather(*(one(client, m) for m in models())))
