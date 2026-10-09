from agent.agent import trace
from agent.explain import explain_saved


def test_trace_pairs_tool_use_with_tool_result():
    messages = [
        {"role": "assistant", "content": [{"toolUse": {"toolUseId": "1", "name": "score_routes", "input": {"mode": "cycle"}}}]},
        {"role": "user", "content": [{"toolResult": {"toolUseId": "1", "content": [{"text": "{\"routes\":[]}"}]}}]},
    ]
    calls = trace(messages)
    assert calls == [{"name": "score_routes", "input": {"mode": "cycle"}, "output": "{\"routes\":[]}"}]


def test_explain_uses_only_the_saved_numbers():
    summary = {
        "recommended": {"route_id": "r2", "wait_min": 40, "exposure_index": 70, "mean_pm25": 55, "confidence": 0.8},
        "baseline": {"route_id": "r1", "duration_min": 30, "exposure_index": 100},
        "delta": {"exposure_index_pct": -30.0, "arrival_min": 12},
        "preference": {"sensitivity": "sensitive", "max_extra_min": 15, "max_wait_min": 120},
        "data_age_min": 20,
        "snapshot": None,
    }
    text = explain_saved(summary)
    assert "r2" in text and "40" in text and "30.0" in text
    assert "99" not in text
