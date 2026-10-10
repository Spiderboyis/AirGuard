"""Deterministic explanation of a trip result, used when the language model is unavailable or
produces a number no tool returned. Same facts, plainer wording, zero chance of invention."""

from __future__ import annotations

from airguard.agent.summaries import trip_summary


def _pct(v: float) -> str:
    return f"{abs(v):.0f}%"


def explain_trip(t: dict) -> str:
    s = trip_summary(t)
    rec, base, ch = s["recommended"], s["fastest_leaving_now"], s["change_vs_fastest_now"]
    lines = []
    kind = t["decision"]["kind"]
    if kind == "stay":
        lines.append(f"Leave now on **{base['route']}** ({base['duration_min']} min). None of the other "
                     f"routes or later departures cut your exposure enough to be worth the extra time "
                     f"for a {t['sensitivity']} profile.")
    else:
        when = "now" if rec["wait_min"] == 0 else f"at **{rec['leave_at_ist']}** ({rec['wait_min']} min from now)"
        lines.append(f"Leave {when} on **{rec['route']}**. Compared with the fastest route leaving now, "
                     f"your exposure index drops by **{_pct(ch['exposure_pct'])}** "
                     f"({base['exposure_index']} → {rec['exposure_index']}) and you arrive "
                     f"**{ch['arrival_later_min']:g} min** later.")
    lines.append(f"Average PM2.5 on that trip: about {rec['avg_pm25']} µg/m³ ({_level(t)}). "
                 f"Forecast range for the exposure index: {rec['exposure_range'][0]}–{rec['exposure_range'][1]}. "
                 f"Confidence {rec['confidence']:.2f} (higher is better; it falls with distance from monitors "
                 f"and forecast uncertainty).")
    low = s["lowest_possible_in_window"]
    if low["exposure_index"] < rec["exposure_index"]:
        lim = t["limits"]
        extra = low["duration_min"] - base["duration_min"]
        outside = low["wait_min"] > lim["max_wait_min"] or extra > lim["max_extra_min"]
        why = ("it falls outside your time limits" if outside
               else f"the saving isn't worth the extra time for a {t['sensitivity']} profile")
        lines.append(f"The cleanest option in the window is {low['route']} at {low['leave_at_ist']} "
                     f"(index {low['exposure_index']}), but {why}.")
    d = s["data"]
    if d["stations_with_delayed_feed"]:
        lines.append(f"Note: {d['stations_with_delayed_feed']} of {d['stations']} stations have a delayed feed, "
                     f"so their values are model estimates.")
    lines.append("This is general guidance based on a forecast, not medical advice.")
    return "\n\n".join(lines)


def _level(t: dict) -> str:
    return t["recommended_route"]["risk_label"].lower()
