"""Fill a short recommendation from numbers the engine already computed.

Used for the offline demo file and as a last resort while snapshotting when the
model is down. It does not invent a figure that is not in the saved trip.
"""


def explain_saved(summary: dict) -> str:
    rec = summary["recommended"]
    base = summary["baseline"]
    delta = summary["delta"]
    pref = summary.get("preference") or {}
    pct = delta.get("exposure_index_pct") or 0
    if pct < 0:
        direction = "lower"
    elif pct > 0:
        direction = "higher"
    else:
        direction = "unchanged"
    wait = rec.get("wait_min") or 0
    when = f" and leave {wait} minutes later" if wait else ""
    lines = [
        f"Take route {rec.get('route_id')}{when}: estimated exposure is {abs(pct)}% {direction} for {delta.get('arrival_min')} extra minutes in total.",
        f"- The fastest leave-now option is route {base.get('route_id')} at {base.get('duration_min')} minutes with exposure index {base.get('exposure_index')}.",
        f"- The recommended option has exposure index {rec.get('exposure_index')}, average PM2.5 {rec.get('mean_pm25')} µg/m³, and data reliability {rec.get('confidence')}.",
    ]
    snap = summary.get("snapshot")
    if snap:
        lines.append(f"- These figures come from a frozen demo snapshot captured at {snap.get('captured_at')}, not from live data.")
    age = summary.get("data_age_min")
    if age is not None:
        lines.append(f"- Air readings are about {age} minutes old.")
    lines.append(
        f"- Sensitivity {pref.get('sensitivity', 'normal')}: up to {pref.get('max_extra_min')} extra minutes and a wait up to {pref.get('max_wait_min')} minutes. Sensitivity does not change the exposure estimate."
    )
    lines.append("- This is exposure guidance under stated assumptions, not medical advice.")
    return "\n".join(lines)
