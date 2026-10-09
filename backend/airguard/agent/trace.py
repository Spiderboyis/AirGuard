"""Per-request record of tool calls, so the UI can show exactly what the agent did."""

from __future__ import annotations

import asyncio
import contextvars
import functools
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Trace:
    calls: list[dict] = field(default_factory=list)
    loop: asyncio.AbstractEventLoop | None = None
    queue: asyncio.Queue | None = None

    def emit(self, event: dict) -> None:
        if self.loop and self.queue:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, event)


current: contextvars.ContextVar[Trace | None] = contextvars.ContextVar("airguard_trace", default=None)


def traced(fn: Callable) -> Callable:
    """Record name, input, output, duration and success of every call to `fn`."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        tr = current.get()
        inputs = {**{f"arg{i}": a for i, a in enumerate(args)}, **kwargs}
        # Small models sometimes repeat an identical call; hand back the earlier result and a nudge.
        if tr:
            prev = next((c for c in tr.calls if c["name"] == fn.__name__ and c["input"] == inputs and c["ok"]), None)
            if prev is not None:
                return json.dumps({"note": "You already have this result. Answer the user now.",
                                   "result": prev["output"]}, ensure_ascii=False, default=str)
        if tr:
            tr.emit({"type": "tool_start", "name": fn.__name__, "input": inputs})
        t0 = time.monotonic()
        ok = True
        try:
            out: Any = fn(*args, **kwargs)
        except Exception as e:  # the model sees the error text and can say so plainly
            ok = False
            out = {"error": str(e) or e.__class__.__name__}
        ms = int((time.monotonic() - t0) * 1000)
        if tr:
            call = {"name": fn.__name__, "input": inputs, "output": out, "ms": ms, "ok": ok}
            tr.calls.append(call)
            tr.emit({"type": "tool_end", **call})
        return json.dumps(out, ensure_ascii=False, default=str)

    return wrapper
