"""Runs the storage layer against a fake Turso endpoint backed by SQLite, in the HTTP pipeline format."""

import asyncio
import json
import sqlite3

import httpx
import pytest

from billbreaker import db
from billbreaker.db_turso import TursoClient
from billbreaker.services import analysis_cache, rate_limit, shares


def fake_turso():
    conn = sqlite3.connect(":memory:", isolation_level=None)
    seen = []

    def cell(v):
        if v is None:
            return {"type": "null"}
        if isinstance(v, int):
            return {"type": "integer", "value": str(v)}
        if isinstance(v, float):
            return {"type": "float", "value": v}
        return {"type": "text", "value": v}

    def arg(a):
        return {"integer": lambda: int(a["value"]), "float": lambda: a["value"], "null": lambda: None}.get(
            a["type"], lambda: a["value"]
        )()

    def handler(request: httpx.Request):
        assert request.url.path == "/v2/pipeline"
        assert request.headers["authorization"] == "Bearer secret"
        results = []
        for req in json.loads(request.content)["requests"]:
            if req["type"] == "close":
                results.append({"type": "ok", "response": {"type": "close"}})
                continue
            stmt = req["stmt"]
            seen.append(stmt["sql"])
            try:
                cur = conn.execute(stmt["sql"], [arg(a) for a in stmt.get("args", [])])
            except sqlite3.Error as exc:
                results.append({"type": "error", "error": {"message": str(exc)}})
                continue
            cols = [{"name": d[0]} for d in cur.description or []]
            rows = [[cell(v) for v in r] for r in cur.fetchall()]
            results.append({"type": "ok", "response": {"type": "execute", "result": {"cols": cols, "rows": rows}}})
        return httpx.Response(200, json={"baton": None, "results": results})

    return httpx.MockTransport(handler), seen


@pytest.fixture
def turso(monkeypatch):
    transport, seen = fake_turso()
    monkeypatch.setattr(db, "_db", TursoClient("libsql://bb.turso.io", "secret", db.SCHEMA, transport))
    return seen


def test_shares_round_trip(turso):
    slug = asyncio.run(shares.create("US", "HR1", "Title", None, {"quick": {"tldr": "hi"}}))
    row = asyncio.run(shares.get(slug))
    assert row["title"] == "Title"
    assert row["payload"] == {"quick": {"tldr": "hi"}}


def test_cache_round_trip(turso):
    asyncio.run(analysis_cache.save("US", "HR1", "h", "T", None, [{"event": "quick_take", "data": {}}]))
    assert asyncio.run(analysis_cache.load_fresh("US", "HR1", "h"))["title"] == "T"


def test_rate_limit_counts_and_blocks(turso):
    results = [asyncio.run(rate_limit._bump("ip:x", 2, 60)) for _ in range(3)]
    assert [r.count for r in results] == [1, 2, 3]
    assert [r.allowed for r in results] == [True, True, False]


def test_schema_is_created_once(turso):
    asyncio.run(shares.get("abcdefgh"))
    asyncio.run(shares.get("abcdefgh"))
    assert sum(1 for s in turso if s.startswith("CREATE TABLE IF NOT EXISTS shared_analyses")) == 1


def test_errors_surface(turso):
    with pytest.raises(Exception, match="no such table"):
        asyncio.run(db.query("SELECT * FROM missing"))
