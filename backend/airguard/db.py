"""Thin Postgres access layer (works the same against local and hosted Supabase).

Uses one shared connection per process. Request handlers and batch jobs call `query`, `execute`
and `upsert`; nothing else in the codebase talks to the database directly.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable, Sequence
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb  # re-exported for callers

from airguard.config import settings


class DatabaseUnavailable(RuntimeError):
    """The database could not be reached."""


_lock = threading.Lock()
_conn: psycopg.Connection | None = None


def _connection() -> psycopg.Connection:
    global _conn
    if _conn is None or _conn.closed:
        try:
            _conn = psycopg.connect(settings().database_url, autocommit=True, row_factory=dict_row, connect_timeout=5)
        except psycopg.OperationalError as e:
            raise DatabaseUnavailable(str(e)) from e
    return _conn


def _run(fn):
    global _conn
    with _lock:
        for attempt in range(2):
            try:
                return fn(_connection())
            except psycopg.OperationalError as e:  # dropped connection: reconnect once
                _conn = None
                if attempt == 1:
                    raise DatabaseUnavailable(str(e)) from e
    return None


def query(sql: str, params: Sequence[Any] | dict | None = None) -> list[dict]:
    def go(c: psycopg.Connection):
        with c.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else []

    return _run(go)


def execute(sql: str, params: Sequence[Any] | dict | None = None) -> None:
    def go(c: psycopg.Connection):
        with c.cursor() as cur:
            cur.execute(sql, params)

    _run(go)


def upsert(table: str, rows: Iterable[dict], conflict: Sequence[str], update: Sequence[str] | None = None,
           chunk: int = 5000) -> int:
    """Insert rows, updating `update` columns (default: all non-key columns) on conflict.

    Rows are de-duplicated on the conflict key first (last one wins), because Postgres rejects a
    single statement that touches the same row twice.
    """
    rows = list(rows)
    if not rows:
        return 0
    cols = list(rows[0].keys())
    unique = {tuple(r.get(k) for k in conflict): r for r in rows}
    rows = list(unique.values())
    update = [c for c in (update if update is not None else cols) if c not in conflict]
    col_sql = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    set_sql = ", ".join(f"{c} = excluded.{c}" for c in update)
    action = f"do update set {set_sql}" if set_sql else "do nothing"
    sql = (f"insert into {table} ({col_sql}) values ({placeholders}) "
           f"on conflict ({', '.join(conflict)}) {action}")

    def adapt(v):
        return Jsonb(v) if isinstance(v, (dict, list)) else v

    def go(c: psycopg.Connection):
        with c.cursor() as cur:
            for i in range(0, len(rows), chunk):
                batch = [tuple(adapt(r.get(k)) for k in cols) for r in rows[i:i + chunk]]
                cur.executemany(sql, batch)

    _run(go)
    return len(rows)


def ping() -> bool:
    try:
        query("select 1 as ok")
        return True
    except DatabaseUnavailable:
        return False
