"""
Storage for the analysis cache, shared pages, rate limits and sync copies.

Two interchangeable backends with the same SQL: a local SQLite file for
development and tests, and a hosted Turso (libSQL) database over HTTP when
TURSO_DATABASE_URL is set, as on Vercel where the disk does not persist.
"""

import asyncio
import sqlite3
from pathlib import Path

from .config import settings
from .db_turso import TursoClient

SCHEMA = """
CREATE TABLE IF NOT EXISTS bill_analyses (
  state TEXT NOT NULL,
  bill_no TEXT NOT NULL,
  text_hash TEXT NOT NULL,
  title TEXT,
  source_url TEXT,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  PRIMARY KEY (state, bill_no, text_hash)
);
CREATE TABLE IF NOT EXISTS shared_analyses (
  slug TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  bill_no TEXT NOT NULL,
  title TEXT,
  source_url TEXT,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rate_limits (
  identifier TEXT PRIMARY KEY,
  window_start REAL NOT NULL,
  count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS abuse_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  identifier TEXT NOT NULL,
  endpoint TEXT,
  reason TEXT NOT NULL,
  count INTEGER NOT NULL,
  limit_value INTEGER NOT NULL,
  window_seconds INTEGER NOT NULL,
  meta TEXT
);
CREATE TABLE IF NOT EXISTS device_watchlist (
  device_id TEXT NOT NULL,
  state TEXT NOT NULL,
  bill_no TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  added_at TEXT NOT NULL,
  PRIMARY KEY (device_id, state, bill_no)
);
"""


class LocalDatabase:
    def __init__(self, path: Path | str):
        path = Path(path)
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._lock = asyncio.Lock()

    async def query(self, sql: str, params: tuple = ()) -> list[dict]:
        async with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    async def batch(self, sql: str, rows: list[tuple]) -> None:
        async with self._lock:
            self._conn.executemany(sql, rows)


_db: LocalDatabase | TursoClient | None = None


def use_database(path: Path | str) -> None:
    """Points the app at another local database file (tests use ':memory:')."""
    global _db
    _db = LocalDatabase(path)


def _current():
    global _db
    if _db is None:
        if settings.turso_url:
            _db = TursoClient(settings.turso_url, settings.turso_token, SCHEMA)
        else:
            _db = LocalDatabase(settings.database_path)
    return _db


async def query(sql: str, params: tuple = ()) -> list[dict]:
    """Runs one statement and returns its rows (empty for writes without RETURNING)."""
    return await _current().query(sql, params)


async def query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = await query(sql, params)
    return rows[0] if rows else None


async def execute(sql: str, params: tuple = ()) -> None:
    await query(sql, params)


async def batch(sql: str, rows: list[tuple]) -> None:
    """Runs one statement once per row, in a single round trip."""
    if rows:
        await _current().batch(sql, rows)
