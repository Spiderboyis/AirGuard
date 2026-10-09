import json
import os

from strands import Agent

from agent.tools import TOOLS, reset_demo, set_demo

SYSTEM_PROMPT = """You are AirGuard, a trip assistant that helps people in Delhi NCR choose routes and departure times that lower their exposure to PM2.5 air pollution.

Rules:
1. Every number you state (PM2.5, minutes, exposure index, percentages) must come from a tool result in this conversation. Never estimate or recall numbers from memory. If you lack a number, call a tool or say you cannot tell.
2. If the message starts with a '[Current trip id: ...]' line, call get_trip_result first and answer from it; do not recompute that trip. To compare routes for a different trip call score_routes. To suggest when to leave call best_departure_time. Call geocode first when the user names places. Scheduled departure times are not supported in v1: AirGuard compares leaving now with waiting and leaving later, within the next few hours. If the user names a specific later clock time, say so and answer for leaving now versus waiting. Use now_ist only to say which clock time a recommended wait corresponds to. In a frozen demo snapshot, now_ist returns the snapshot's capture time, so give waits as minutes after that time.
3. Exposure is an index for comparing options under stated assumptions, not a measured dose. Say 'estimated exposure' and express differences as percentages between options. Never describe a level as an official AQI category.
4. Always mention the reliability score and the data age in plain words. If the trip result says it comes from a demo snapshot, say it is a frozen snapshot captured at the stated time, not live data. If reliability is below 0.5 or data_age_min is above 180, say the estimate is uncertain and why.
5. The recommendation comes from the tool's decision rule, which uses the profile's sensitivity and the user's limits on extra minutes and waiting. Pass max_extra_min and max_wait_min from the profile line into best_departure_time. Report the recommended option, its time cost in minutes, and the limits that were used; never pick a different option yourself.
6. Adapt to the profile line at the start of the message. For sensitivity 'sensitive' or 'high', pass the sensitivity to best_departure_time (it changes how much extra time the decision rule accepts, never the exposure estimate) and note that general guidance is to limit hard exertion outdoors on high-pollution days. Do not diagnose, give medical advice, or mention medication; suggest a doctor for health concerns.
7. Keep answers short: a one-line recommendation first, then at most four bullets with the numbers behind it. No tables.
8. If a tool returns an error, say in one sentence what failed and what the user can try.
9. Only Delhi NCR and the modes walk, cycle and car are supported."""


def make_model():
    if os.environ.get("LLM_BACKEND", "bedrock") == "ollama":
        from strands.models.ollama import OllamaModel
        return OllamaModel(
            host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
            model_id=os.environ.get("OLLAMA_MODEL", "llama3.1"),
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
                calls[ident] = {"name": used.get("name"), "input": _safe(used.get("input")), "output": None}
            elif "toolResult" in block:
                result = block["toolResult"]
                ident = result.get("toolUseId")
                text = _result_text(result.get("content"))
                if ident in calls:
                    calls[ident]["output"] = text
                else:
                    order.append(ident)
                    calls[ident] = {"name": result.get("name") or "tool", "input": None, "output": text}
    return [calls[ident] for ident in order if ident in calls]


def chat(message, profile=None, history=None, demo=False, trip_id=None):
    token = set_demo(demo)
    try:
        ctx = ""
        if profile:
            ctx = (
                f"[Profile: sensitivity={profile.get('sensitivity', 'normal')}, "
                f"usual mode={profile.get('mode', 'walk')}, "
                f"max_extra_min={profile.get('max_extra_min', 15)}, "
                f"max_wait_min={profile.get('max_wait_min', 120)}]\n"
            )
        if trip_id:
            ctx += f"[Current trip id: {trip_id}]\n"
        agent = Agent(
            model=make_model(),
            system_prompt=SYSTEM_PROMPT,
            tools=TOOLS,
            callback_handler=None,
            messages=history or [],
        )
        start = len(agent.messages)
        result = agent(ctx + message)
        return {"answer": str(result).strip(), "tool_calls": trace(agent.messages[start:]), "cached": False}
    finally:
        reset_demo(token)
