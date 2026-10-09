"""The AirGuard assistant: a Strands agent that answers commute questions using only tool outputs.

Flow for one message:
1. Build a Strands Agent with the six tools and a system prompt that carries the user's profile
   and the trip they are looking at.
2. Run it (streaming tool calls and text to the UI as they happen).
3. Check every number in the answer against the tool outputs (guard.check). If anything is
   ungrounded, or the model is unreachable, answer with the deterministic explanation instead and
   say so (`source="fallback"`).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator

from airguard.agent import explain, guard
from airguard.agent.prompt import system_prompt
from airguard.agent.tools import get_trip_result, tools_for
from airguard.agent.trace import Trace, current
from airguard.config import settings
from airguard.services import trips

log = logging.getLogger("airguard.agent")

THINK = re.compile(r"<think>.*?</think>", re.S)


def _model():
    cfg = settings()
    if cfg.llm_backend == "ollama":
        from strands.models.ollama import OllamaModel

        return OllamaModel(host=cfg.ollama_host, model_id=cfg.ollama_model, temperature=0.2, max_tokens=700,
                           keep_alive="30m", additional_args={"think": False})
    if cfg.llm_backend == "bedrock":
        from strands.models import BedrockModel

        return BedrockModel(model_id=cfg.bedrock_model_id, region_name=cfg.aws_region, temperature=0.2,
                            max_tokens=700)
    return None


def model_label() -> str | None:
    cfg = settings()
    return {"ollama": f"ollama/{cfg.ollama_model}", "bedrock": f"bedrock/{cfg.bedrock_model_id}"}.get(cfg.llm_backend)


def _history_messages(history: list[dict]) -> list[dict]:
    return [{"role": h["role"], "content": [{"text": h["content"]}]} for h in history[-6:] if h.get("content")]


def _fallback(message: str, trip_id: str | None, tr: Trace, reason: str) -> dict:
    """Answer without the model: explain the current trip, or say plainly what we can't do."""
    t = trips.get(trip_id) if trip_id else None
    if t is not None:
        if not any(c["name"] == "get_trip_result" for c in tr.calls):
            token = current.set(tr)
            try:
                get_trip_result(trip_id)  # recorded in the trace like any other tool call
            finally:
                current.reset(token)
        answer = explain.explain_trip(t)
    else:
        answer = ("I can't reach the language model right now. Plan a trip on the left and I'll explain "
                  "the result from the saved analysis.")
    log.info("fallback answer (%s)", reason)
    return {"answer": answer, "source": "fallback", "fallback_reason": reason}


def _finish(text: str, message: str, trip_id: str | None, tr: Trace) -> dict:
    text = THINK.sub("", text).strip()
    ok, bad = guard.check(text, [c["output"] for c in tr.calls], message)
    last_failed = bool(tr.calls) and not tr.calls[-1]["ok"]
    if text and ok and not (trip_id and last_failed):
        return {"answer": text, "source": "model", "grounded": True, "ungrounded_numbers": []}
    if not text:
        reason = "empty answer"
    elif not ok:
        reason = f"ungrounded numbers: {', '.join(bad)}"
    else:
        reason = f"tool {tr.calls[-1]['name']} failed"
    out = _fallback(message, trip_id, tr, reason)
    out.update(grounded=True, ungrounded_numbers=bad)
    return out


async def stream(message: str, profile: dict | None, trip_id: str | None,
                 history: list[dict]) -> AsyncIterator[dict]:
    """Yield UI events: tool_start, tool_end, token, and finally done."""
    loop = asyncio.get_running_loop()
    tr = Trace(loop=loop, queue=asyncio.Queue())
    token = current.set(tr)
    model = _model()
    started = time.monotonic()
    try:
        if model is None:
            result = _fallback(message, trip_id, tr, "no language model configured")
            result.update(grounded=True, ungrounded_numbers=[])
        else:
            from strands import Agent

            agent = Agent(model=model, tools=tools_for(trip_id), system_prompt=system_prompt(profile, trip_id),
                          messages=_history_messages(history), callback_handler=None)
            text_parts: list[str] = []
            done = asyncio.Event()
            error: list[BaseException] = []

            async def run(prompt: str):
                try:
                    async for ev in agent.stream_async(prompt):
                        if "data" in ev and isinstance(ev["data"], str):
                            text_parts.append(ev["data"])
                            tr.queue.put_nowait({"type": "token", "text": ev["data"]})
                        if "message" in ev and ev["message"].get("role") == "assistant":
                            # A new assistant turn after tool use: drop text produced before the tool call.
                            if any("toolUse" in c for c in ev["message"].get("content", [])):
                                text_parts.clear()
                                tr.queue.put_nowait({"type": "reset"})
                except BaseException as e:  # surfaced below as a fallback
                    error.append(e)
                finally:
                    done.set()

            for attempt in range(2):
                done.clear()
                task = asyncio.create_task(run(message if attempt == 0 else (
                    f"First call get_trip_result with trip_id={trip_id}, then answer: {message}")))
                while not (done.is_set() and tr.queue.empty()):
                    try:
                        ev = await asyncio.wait_for(tr.queue.get(), timeout=0.2)
                        yield ev
                    except TimeoutError:
                        continue
                await task
                # Small models sometimes answer a follow-up from memory; with a trip on screen, insist once.
                if error or tr.calls or not trip_id:
                    break
                text_parts.clear()
                tr.queue.put_nowait({"type": "reset"})
            if error:
                log.warning("agent failed: %r", error[0])
                result = _fallback(message, trip_id, tr, f"model error: {error[0].__class__.__name__}")
                result.update(grounded=True, ungrounded_numbers=[])
            else:
                result = _finish("".join(text_parts), message, trip_id, tr)
        while not tr.queue.empty():
            yield tr.queue.get_nowait()
        yield {"type": "done", **result, "tool_calls": tr.calls, "model": model_label() if model else None,
               "ms": int((time.monotonic() - started) * 1000)}
    finally:
        current.reset(token)


async def chat(message: str, profile: dict | None, trip_id: str | None, history: list[dict]) -> dict:
    final: dict = {}
    async for ev in stream(message, profile, trip_id, history):
        if ev["type"] == "done":
            final = ev
    final.pop("type", None)
    return final
