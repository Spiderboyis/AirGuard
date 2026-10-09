import base64
import hashlib
import json
import os
import time

from agent.agent import chat
from common import db

_hits: dict[str, list[float]] = {}


def _allow_origin(origin: str) -> str:
    allowed = [item.strip() for item in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if item.strip()]
    if not allowed or "*" in allowed:
        return "*"
    return origin if origin in allowed else allowed[0]


def _resp(code, body, origin, extra=None):
    headers = {
        "content-type": "application/json",
        "access-control-allow-origin": _allow_origin(origin),
        "access-control-allow-methods": "POST, OPTIONS",
        "access-control-allow-headers": "content-type",
    }
    if extra:
        headers.update(extra)
    return {"statusCode": code, "headers": headers, "body": "" if body is None else json.dumps(body)}


def _cached(msg):
    key = "agent:" + hashlib.sha1(msg.strip().lower().encode()).hexdigest()
    hit = db.select("route_cache", select="response", key=f"eq.{key}")
    return hit[0]["response"] if hit else None


def _history(items):
    if not isinstance(items, list):
        return []
    return [
        {"role": item["role"], "content": [{"text": str(item["text"])[:1000]}]}
        for item in items
        if isinstance(item, dict) and item.get("role") in ("user", "assistant") and item.get("text")
    ]


def _limited(ip: str, limit: int = 10, window: float = 60) -> bool:
    now = time.time()
    recent = [stamp for stamp in _hits.get(ip, []) if now - stamp < window]
    if len(recent) >= limit:
        _hits[ip] = recent
        return False
    recent.append(now)
    _hits[ip] = recent
    return True


def lambda_handler(event, context):
    del context
    headers = {str(k).lower(): v for k, v in (event.get("headers") or {}).items()}
    origin = headers.get("origin", "") or ""
    method = ((event.get("requestContext") or {}).get("http") or {}).get("method", "POST")
    if method == "OPTIONS":
        return _resp(204, None, origin, {"access-control-max-age": "600"})
    ip = ((event.get("requestContext") or {}).get("http") or {}).get("sourceIp", "unknown")
    if not _limited(ip):
        return _resp(429, {"error": {"code": "rate_limited", "message": "Too many assistant requests. Wait a minute and try again."}}, origin)
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded") and raw:
        raw = base64.b64decode(raw).decode()
    try:
        body = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return _resp(400, {"error": {"code": "invalid_input", "message": "Request body must be JSON."}}, origin)
    if not isinstance(body, dict):
        return _resp(400, {"error": {"code": "invalid_input", "message": "Request body must be a JSON object."}}, origin)
    msg = (body.get("message") or "").strip()
    if not 1 <= len(msg) <= 500:
        return _resp(400, {"error": {"code": "invalid_input", "message": "Message must be 1 to 500 characters."}}, origin)
    profile = body.get("profile") if isinstance(body.get("profile"), dict) else None
    try:
        out = chat(msg, profile, _history((body.get("history") or [])[-6:]), bool(body.get("demo")), body.get("trip_id"))
        return _resp(200, out, origin)
    except Exception as exc:
        print("agent failed:", repr(exc))
        hit = _cached(msg) if body.get("demo") else None
        if hit:
            return _resp(200, {**hit, "cached": True}, origin)
        return _resp(503, {"error": {"code": "agent_unavailable", "message": "The assistant is unavailable right now. The route and departure results still work."}}, origin)
