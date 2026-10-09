import json
import os
import re

from strands import Agent

from agent.tools import TOOLS, reset_demo, set_demo

SYSTEM_PROMPT = """You are AirGuard, an intelligent clean-air transit copilot for Delhi NCR that helps travelers choose the healthiest routes and optimal departure windows to minimize PM2.5 inhalation.

Rules:
1. Every factual number (PM2.5, minutes, distance, percentages) must come directly from a tool result in this conversation. Never guess, assume, or hallucinate numbers.
2. Routing & Trip Resolution Priority:
   a. If '[Current trip id: ...]' is present, you MUST immediately call get_trip_result(trip_id=...) and answer directly from the evaluated routes and recommendation. DO NOT ask the user for places or locations.
   b. If '[Current planned trip: from=..., to=...]' is present and no trip id exists, call evaluate_trip(from_place=..., to_place=...). Do not ask for origin or destination.
   c. If places or landmarks are mentioned in the message, call evaluate_trip(from_place=..., to_place=...).
   d. If the user asks about air quality at a specific location, call geocode then get_forecast.
   e. Only ask the user for locations if no trip id, planned trip, or place names exist in the conversation.
3. Response Formatting & Structure:
   Provide concise, high-value, easy-to-read responses formatted with clean markdown:
   - Direct Recommendation: Begin with a direct 1-2 sentence recommendation stating the cleanest route and the departure action.
   - Route Breakdown: Summarize the cleanest option vs alternatives (route name, duration in minutes, distance in km, average PM2.5 in µg/m³, risk tier, and exposure difference).
   - Departure Timing: Clearly state whether to depart immediately or wait. Explain the ambient PM2.5 trend (e.g. why waiting is or isn't beneficial). Never output repetitive 0% lines.
   - Health Guidance: Add 1-2 practical tips tailored to the user's sensitivity (e.g. N95 mask advice for pedestrians/cyclists in elevated/high PM2.5, keeping car windows closed with AC recirculation, or taking lower-traffic corridors).
4. Exposure Index: This is a relative exposure metric (PM2.5 × minutes × breathing intake factor) designed to rank transit alternatives. Explain exposure reductions clearly as percentages (e.g., 'Route 3 lowers your estimated PM2.5 exposure by 28% compared to Route 1').
5. Departure Timing: Scheduled clock times are not supported; explain the trade-off between leaving immediately vs waiting up to a few hours. Use now_ist if helpful to give the current IST time.
6. Only Delhi NCR and modes walk, cycle, and car are supported."""



class _ToolFunc:
    def __init__(self, name, args):
        self.name = name
        self.arguments = args


class _MockToolCall:
    def __init__(self, name, args):
        self.function = _ToolFunc(name, args)


def _parse_tool_json(text):
    if not text:
        return None, None
    raw = text.strip()

    # Strip code block wrappers
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    # Search for <tool_call> tags
    tc = re.search(r"<tool_call>\s*(.*?)\s*</tool_call>", raw, re.DOTALL)
    if tc:
        raw = tc.group(1).strip()

    # Regex search for {"name": "...", "arguments": {...}}
    match = re.search(
        r'\{\s*"name"\s*:\s*"([a-zA-Z0-9_]+)"\s*,\s*"arguments"\s*:\s*(\{.*?\})\s*\}',
        raw,
        re.DOTALL,
    )
    if match:
        try:
            return match.group(1), json.loads(match.group(2))
        except Exception:
            pass

    # Try standard JSON parsing
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict) and "name" in obj and "arguments" in obj:
            args = obj["arguments"]
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass
            return str(obj["name"]), args if isinstance(args, dict) else {}
    except Exception:
        pass

    return None, None


def make_model():
    if os.environ.get("LLM_BACKEND", "bedrock") == "ollama":
        import ollama
        from strands.models.ollama import OllamaModel

        class SmartOllamaModel(OllamaModel):
            async def stream(
                self,
                messages,
                tool_specs=None,
                system_prompt=None,
                tool_choice=None,
                **kwargs,
            ):
                request = self.format_request(messages, tool_specs, system_prompt)
                client = ollama.AsyncClient(self.host, **self.client_args)

                tool_calls_found = []
                text_accum = []
                event = None

                response = await client.chat(**request)
                async for event in response:
                    if event.message.tool_calls:
                        for tc in event.message.tool_calls:
                            tool_calls_found.append(tc)
                    if event.message.content:
                        text_accum.append(event.message.content)

                full_text = "".join(text_accum).strip()

                # If Ollama didn't parse tool_calls into message.tool_calls, check if the model emitted a tool JSON
                if not tool_calls_found and tool_specs:
                    t_name, t_args = _parse_tool_json(full_text)
                    if t_name:
                        valid_names = [ts["name"] for ts in tool_specs]
                        if t_name in valid_names:
                            tool_calls_found.append(_MockToolCall(t_name, t_args or {}))

                yield self.format_chunk({"chunk_type": "message_start"})

                if tool_calls_found:
                    for tc in tool_calls_found:
                        yield self.format_chunk(
                            {"chunk_type": "content_start", "data_type": "tool", "data": tc}
                        )
                        yield self.format_chunk(
                            {"chunk_type": "content_delta", "data_type": "tool", "data": tc}
                        )
                        yield self.format_chunk(
                            {"chunk_type": "content_stop", "data_type": "tool", "data": tc}
                        )
                    yield self.format_chunk({"chunk_type": "message_stop", "data": "tool_use"})
                else:
                    yield self.format_chunk({"chunk_type": "content_start", "data_type": "text"})
                    yield self.format_chunk(
                        {"chunk_type": "content_delta", "data_type": "text", "data": full_text}
                    )
                    yield self.format_chunk({"chunk_type": "content_stop", "data_type": "text"})
                    yield self.format_chunk(
                        {
                            "chunk_type": "message_stop",
                            "data": event.done_reason if event else "end_turn",
                        }
                    )

        return SmartOllamaModel(
            host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            model_id=os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b"),
            temperature=0.1,
        )

    from strands.models import BedrockModel

    return BedrockModel(
        model_id=os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-2-lite-v1:0"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        temperature=0.2,
    )


def _safe(value):
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _result_text(content):
    parts = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            if "text" in block:
                parts.append(str(block.get("text") or ""))
            elif "json" in block:
                parts.append(json.dumps(block["json"], default=str))
    return " ".join(part for part in parts if part)[:2000]


def trace(messages):
    """Pull tool calls and their results out of Strands messages."""
    calls = {}
    order = []
    for message in messages or []:
        content = message.get("content", []) if isinstance(message, dict) else []
        for block in content:
            if not isinstance(block, dict):
                continue
            if "toolUse" in block:
                used = block["toolUse"]
                ident = used.get("toolUseId")
                if ident not in calls:
                    order.append(ident)
                calls[ident] = {
                    "name": used.get("name"),
                    "input": _safe(used.get("input")),
                    "output": None,
                }
            elif "toolResult" in block:
                result = block["toolResult"]
                ident = result.get("toolUseId")
                text = _result_text(result.get("content"))
                if ident in calls:
                    calls[ident]["output"] = text
                else:
                    order.append(ident)
                    calls[ident] = {
                        "name": result.get("name") or "tool",
                        "input": None,
                        "output": text,
                    }
    return [calls[ident] for ident in order if ident in calls]


def chat(
    message,
    profile=None,
    history=None,
    demo=False,
    trip_id=None,
    from_place=None,
    to_place=None,
):
    token = set_demo(demo)
    try:
        ctx_parts = []
        if trip_id:
            ctx_parts.append(f"[Current trip id: {trip_id}]")
        if from_place and to_place:
            ctx_parts.append(f"[Current planned trip: from='{from_place}', to='{to_place}']")
        if profile:
            ctx_parts.append(
                f"[Profile: sensitivity={profile.get('sensitivity', 'normal')}, "
                f"usual mode={profile.get('mode', 'walk')}, "
                f"max_extra_min={profile.get('max_extra_min', 15)}, "
                f"max_wait_min={profile.get('max_wait_min', 120)}]"
            )

        ctx = ("\n".join(ctx_parts) + "\n\n") if ctx_parts else ""

        agent = Agent(
            model=make_model(),
            system_prompt=SYSTEM_PROMPT,
            tools=TOOLS,
            callback_handler=None,
            messages=history or [],
        )
        start = len(agent.messages)
        try:
            result = agent(ctx + message)
            return {
                "answer": str(result).strip(),
                "tool_calls": trace(agent.messages[start:]),
                "cached": False,
            }
        except Exception as exc:
            if trip_id:
                try:
                    from agent.explain import explain_saved
                    from common import db
                    hit = db.select("route_cache", select="response", key=f"eq.trip:{trip_id}")
                    if hit:
                        return {
                            "answer": explain_saved(hit[0]["response"]),
                            "tool_calls": [{"name": "get_trip_result", "input": {"trip_id": trip_id}, "output": "Loaded saved evaluation."}],
                            "cached": True,
                        }
                except Exception:
                    pass
            raise exc
    finally:
        reset_demo(token)
