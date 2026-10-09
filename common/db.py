"""Supabase REST when configured, otherwise a local SQLite file.

The call shape matches the guide (`select` / `upsert` with PostgREST filters) so the
ingestion, training, and API code does not care which backend is live.
"""

import json
import os
import re
import sqlite3
import threading

import httpx

from common.config import cfg

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_OPS = {"eq": "=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "neq": "!="}
_NUMERIC = {
    "stations": {"lat", "lon", "sensor_id"},
    "measurements": {"value"},
    "weather": {"wind_speed", "wind_dir", "humidity", "temp", "blh", "fires_upwind"},
    "forecasts": {"horizon_h", "pm25_pred", "pm25_low", "pm25_high"},
    "forecasts_latest": {"horizon_h", "pm25_pred", "pm25_low", "pm25_high"},
    "eval_metrics": {
        "horizon_h", "mae", "rmse", "baseline_persistence_mae", "baseline_hourly_mean_mae",
        "baseline_persistence_rmse", "baseline_hourly_mean_rmse", "interval_coverage",
        "interval_width", "n_samples",
    },
}

_SCHEMA = """
create table if not exists stations (
  id text primary key,
  name text,
  lat real,
  lon real,
  sensor_id integer,
  last_seen text,
  source text default 'openaq'
);
create table if not exists measurements (
  station_id text not null,
  pollutant text not null,
  value real,
  unit text,
  ts text not null,
  primary key (station_id, pollutant, ts)
);
create table if not exists weather (
  station_id text not null,
  ts text not null,
  wind_speed real,
  wind_dir real,
  humidity real,
  temp real,
  blh real,
  fires_upwind integer,
  primary key (station_id, ts)
);
create table if not exists forecasts (
  station_id text not null,
  horizon_h integer not null,
  target_ts text not null,
  pm25_pred real,
  pm25_low real,
  pm25_high real,
  model_version text not null,
  generated_at text,
  primary key (station_id, horizon_h, target_ts, model_version)
);
create table if not exists forecasts_latest (
  station_id text not null,
  horizon_h integer not null,
  target_ts text not null,
  pm25_pred real,
  pm25_low real,
  pm25_high real,
  model_version text,
  generated_at text,
  primary key (station_id, horizon_h)
);
create table if not exists eval_metrics (
  model_version text not null,
  horizon_h integer not null,
  mae real,
  rmse real,
  baseline_persistence_mae real,
  baseline_hourly_mean_mae real,
  baseline_persistence_rmse real,
  baseline_hourly_mean_rmse real,
  interval_coverage real,
  interval_width real,
  n_samples integer,
  primary key (model_version, horizon_h)
);
create table if not exists route_cache (
  key text primary key,
  response text not null,
  created_at text default (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
create index if not exists measurements_ts on measurements (ts);
"""

_lock = threading.Lock()
_conn = None
_conn_path = None


def pg_filter(expr: str) -> str:
    """Quote PostgREST values that contain reserved characters."""
    op, sep, val = str(expr).partition(".")
    if not sep:
        return str(expr)
    if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
        return f"{op}.{val}"
    if any(ch in val for ch in " ,()"):
        return op + '."' + val.replace('"', '""') + '"'
    return f"{op}.{val}"


def _ident(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"Unsafe SQL name: {name}")
    return name


def _use_supabase() -> bool:
    url = (cfg().get("SUPABASE_URL") or "").strip()
    key = (cfg().get("SUPABASE_SERVICE_KEY") or "").strip()
    if url and not key:
        raise RuntimeError("SUPABASE_URL is set but SUPABASE_SERVICE_KEY is empty.")
    if key and not url:
        raise RuntimeError("SUPABASE_SERVICE_KEY is set but SUPABASE_URL is empty.")
    return bool(url and key)


def reset_connection():
    """Close the cached SQLite connection. Tests use this between databases."""
    global _conn, _conn_path
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
        _conn_path = None


def _connect():
    global _conn, _conn_path
    path = os.path.abspath(os.environ.get("AIRGUARD_DB") or "data/local.db")
    with _lock:
        if _conn is not None and _conn_path == path:
            return _conn
        if _conn is not None:
            _conn.close()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        conn.commit()
        _conn = conn
        _conn_path = path
        return conn


def _h(extra=None):
    key = cfg()["SUPABASE_SERVICE_KEY"]
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", **(extra or {})}


def _url(table):
    return cfg()["SUPABASE_URL"].rstrip("/") + f"/rest/v1/{_ident(table)}"


def _coerce(table, column, val):
    if column not in _NUMERIC.get(table, ()):
        return val
    text = str(val)
    if text == "" or text.lower() == "null":
        return None
    try:
        return float(text) if any(c in text for c in ".eE") else int(text)
    except ValueError:
        return val


def _jsonify(table, rows):
    if table != "route_cache":
        return rows
    out = []
    for row in rows:
        item = dict(row)
        value = item.get("response")
        if isinstance(value, str):
            try:
                item["response"] = json.loads(value)
            except json.JSONDecodeError:
                pass
        out.append(item)
    return out


def _sqlite_select(table, params):
    table = _ident(table)
    cols = params.pop("select", "*")
    order = params.pop("order", None)
    limit = params.pop("limit", None)
    offset = params.pop("offset", None)
    col_sql = "*" if str(cols).strip() == "*" else ",".join(_ident(c.strip()) for c in str(cols).split(",") if c.strip())
    where, values = [], []
    for col, expr in params.items():
        col = _ident(col)
        op, sep, val = str(expr).partition(".")
        if not sep or op not in _OPS:
            raise ValueError(f"Bad filter {col}={expr}")
        if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
            val = val[1:-1].replace('""', '"')
        where.append(f"{col} {_OPS[op]} ?")
        values.append(_coerce(table, col, val))
    sql = f"select {col_sql} from {table}"
    if where:
        sql += " where " + " and ".join(where)
    if order:
        name, _, direction = str(order).partition(".")
        direction = (direction or "asc").lower()
        if direction not in ("asc", "desc"):
            raise ValueError(f"Bad order {order}")
        sql += f" order by {_ident(name)} {direction}"
    if limit is not None:
        sql += " limit ?"
        values.append(int(limit))
    if offset is not None:
        sql += " offset ?"
        values.append(int(offset))
    conn = _connect()
    with _lock:
        fetched = [dict(row) for row in conn.execute(sql, values).fetchall()]
    return _jsonify(table, fetched)


def _sb_select(table, params):
    query = {}
    for key, value in params.items():
        if key in ("select", "order", "limit", "offset"):
            query[key] = value
        else:
            query[key] = pg_filter(str(value))
    response = httpx.get(_url(table), headers=_h(), params=query, timeout=20)
    response.raise_for_status()
    return response.json()


def select(table, **params):
    """select('forecasts', select='*', station_id='eq.123', order='target_ts.asc', limit=100)"""
    params = dict(params)
    if _use_supabase():
        return _sb_select(table, params)
    return _sqlite_select(table, params)


def select_all(table, page=1000, **params):
    """Follow PostgREST's default 1000-row cap until the table is exhausted."""
    out, offset = [], 0
    while True:
        rows = select(table, limit=page, offset=offset, **params)
        out.extend(rows)
        if len(rows) < page:
            return out
        offset += page
        if offset > 1_000_000:
            raise RuntimeError(f"Pagination ran away while reading {table}")


def _dedupe(rows, on_conflict):
    keys = [k.strip() for k in on_conflict.split(",")]
    unique = {tuple(r.get(k) for k in keys): r for r in rows}
    if len(unique) < len(rows):
        print(f"upsert dropped {len(rows) - len(unique)} duplicate rows")
    return list(unique.values()), keys


def _sqlite_upsert(table, rows, keys):
    cols = []
    for row in rows:
        for key in row:
            if key not in cols:
                cols.append(key)
    for key in keys:
        if key not in cols:
            raise ValueError(f"upsert {table}: missing conflict column {key}")
    names = ",".join(_ident(c) for c in cols)
    marks = ",".join("?" for _ in cols)
    updates = [c for c in cols if c not in keys]
    sql = f"insert into {_ident(table)} ({names}) values ({marks})"
    conflict = ",".join(_ident(k) for k in keys)
    if updates:
        sql += f" on conflict({conflict}) do update set " + ",".join(f"{_ident(c)}=excluded.{_ident(c)}" for c in updates)
    else:
        sql += f" on conflict({conflict}) do nothing"
    payload = []
    for row in rows:
        values = []
        for col in cols:
            value = row.get(col)
            if col == "response" and not isinstance(value, (str, type(None))):
                value = json.dumps(value)
            values.append(_plain(value))
        payload.append(values)
    conn = _connect()
    with _lock:
        conn.executemany(sql, payload)
        conn.commit()


def _plain(value):
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except Exception:
            return value
    return value


def _sb_upsert(table, rows, on_conflict, chunk):
    for i in range(0, len(rows), chunk):
        response = httpx.post(
            _url(table),
            headers=_h({"Prefer": "resolution=merge-duplicates,return=minimal"}),
            params={"on_conflict": on_conflict},
            json=rows[i:i + chunk],
            timeout=60,
        )
        response.raise_for_status()


def upsert(table, rows, on_conflict, chunk=500):
    if not rows:
        return
    rows, keys = _dedupe(rows, on_conflict)
    if not rows:
        return
    if _use_supabase():
        _sb_upsert(table, rows, on_conflict, chunk)
        return
    for i in range(0, len(rows), chunk):
        _sqlite_upsert(table, rows[i:i + chunk], keys)
