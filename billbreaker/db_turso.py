"""
Minimal Turso (libSQL) client over its HTTP pipeline API, so no driver is
needed: https://docs.turso.tech/sdk/http/reference
"""

import asyncio

import httpx


def _arg(value) -> dict:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "integer", "value": str(int(value))}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    return {"type": "text", "value": str(value)}


def _value(cell: dict):
    kind, value = cell.get("type"), cell.get("value")
    if kind == "integer":
        return int(value)
    if kind == "float":
        return float(value)
    if kind == "null":
        return None
    return value


def _rows(result: dict) -> list[dict]:
    names = [c["name"] for c in result["cols"]]
    return [dict(zip(names, map(_value, row))) for row in result["rows"]]


class TursoError(Exception):
    pass


class TursoClient:
    def __init__(self, url: str, token: str, schema: str, transport: httpx.AsyncBaseTransport | None = None):
        self._endpoint = url.replace("libsql://", "https://", 1).rstrip("/") + "/v2/pipeline"
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._schema = [s.strip() for s in schema.split(";") if s.strip()]
        self._transport = transport
        self._ready = False
        self._ready_lock = asyncio.Lock()

    async def _pipeline(self, statements: list[dict]) -> list[dict]:
        body = {"requests": [{"type": "execute", "stmt": s} for s in statements] + [{"type": "close"}]}
        async with httpx.AsyncClient(timeout=10, transport=self._transport) as client:
            res = await client.post(self._endpoint, json=body, headers=self._headers)
        if res.status_code != 200:
            raise TursoError(f"Turso returned {res.status_code}")
        results = res.json()["results"][: len(statements)]
        for r in results:
            if r.get("type") == "error":
                raise TursoError(r.get("error", {}).get("message", "query failed"))
        return [r["response"]["result"] for r in results]

    async def _ensure_schema(self) -> None:
        if self._ready:
            return
        async with self._ready_lock:
            if not self._ready:
                await self._pipeline([{"sql": s} for s in self._schema])
                self._ready = True

    async def query(self, sql: str, params: tuple = ()) -> list[dict]:
        await self._ensure_schema()
        (result,) = await self._pipeline([{"sql": sql, "args": [_arg(p) for p in params]}])
        return _rows(result)

    async def batch(self, sql: str, rows: list[tuple]) -> None:
        await self._ensure_schema()
        await self._pipeline([{"sql": sql, "args": [_arg(p) for p in row]} for row in rows])
