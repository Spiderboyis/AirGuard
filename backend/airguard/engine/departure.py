"""Departure optimiser and decision layer.

The optimiser scores every (route, departure) pair on a 15-minute grid. These are scenario
evaluations on top of a forecast issued at +1/+3/+6/+12/+24 h, not 15-minute forecasts.

The decision layer then picks one option. It never changes an exposure number; the user's
sensitivity only sets how many extra minutes a given reduction is worth:

    cost_min  = extra travel minutes + WAIT_COST_WEIGHT * minutes waited
    accept if cost_min <= MINUTES_PER_10PCT[sensitivity] * reduction_pct / 10
              and extra travel <= max_extra_min and wait <= max_wait_min
              and reduction_pct >= MIN_MEANINGFUL_REDUCTION_PCT

The recommendation is the lowest-exposure accepted option. The fastest route leaving now is the
baseline and is always accepted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from airguard.engine import assumptions as A
from airguard.engine.exposure import ForecastUnavailable, PreparedRoute, score
from airguard.engine.field import ForecastField


@dataclass
class DepartureOption:
    wait_min: int
    depart_ts: float
    route_id: str
    label: str
    duration_min: float
    exposure_index: float
    exposure_low: float
    exposure_high: float
    mean_pm25: float
    risk: str
    confidence: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["depart_at"] = datetime.fromtimestamp(self.depart_ts, tz=timezone.utc).isoformat()
        return d


@dataclass
class Decision:
    recommended: DepartureOption
    baseline: DepartureOption
    lowest: DepartureOption               # lowest exposure regardless of the user's limits
    kind: str                             # "stay" | "route" | "wait" | "wait_and_route"
    exposure_change_pct: float            # recommended vs baseline (negative = less exposure)
    arrival_change_min: float             # wait + extra travel
    extra_travel_min: float
    wait_min: int
    accepted_cost_min: float              # what the reduction was worth to this user
    cost_min: float
    sensitivity: str

    def to_dict(self) -> dict:
        return {
            "recommended": self.recommended.to_dict(), "baseline": self.baseline.to_dict(),
            "lowest": self.lowest.to_dict(), "kind": self.kind,
            "delta": {"exposure_index_pct": self.exposure_change_pct, "arrival_min": self.arrival_change_min,
                      "extra_travel_min": self.extra_travel_min, "wait_min": self.wait_min},
            "rule": {"sensitivity": self.sensitivity, "minutes_per_10pct": A.MINUTES_PER_10PCT[self.sensitivity],
                     "cost_min": self.cost_min, "accepted_cost_min": self.accepted_cost_min,
                     "wait_cost_weight": A.WAIT_COST_WEIGHT},
        }


def evaluate(routes: list[PreparedRoute], fld: ForecastField, now_ts: float, mode: str,
             window_h: float = A.DEFAULT_WINDOW_H, step_min: int = A.DEPARTURE_STEP_MIN) -> list[DepartureOption]:
    window_h = min(max(window_h, 0), A.MAX_WINDOW_H)
    options = []
    for wait in range(0, int(window_h * 60) + 1, step_min):
        t = now_ts + wait * 60
        for p in routes:
            try:
                s = score(p, fld, t, mode, with_segments=False)
            except ForecastUnavailable:
                continue
            options.append(DepartureOption(
                wait_min=wait, depart_ts=t, route_id=s.route_id, label=s.label, duration_min=s.duration_min,
                exposure_index=s.exposure_index, exposure_low=s.exposure_low, exposure_high=s.exposure_high,
                mean_pm25=s.mean_pm25, risk=s.risk, confidence=s.confidence))
    if not any(o.wait_min == 0 for o in options):
        raise ForecastUnavailable("the forecast does not cover a departure now")
    return options


def _pct(a: float, b: float) -> float:
    return round((a / b - 1.0) * 100.0, 1) if b > 0 else 0.0


def decide(options: list[DepartureOption], sensitivity: str = "normal", max_extra_min: float = 15,
           max_wait_min: float = 120) -> Decision:
    if sensitivity not in A.MINUTES_PER_10PCT:
        raise ValueError(f"unknown sensitivity {sensitivity!r}")
    k = A.MINUTES_PER_10PCT[sensitivity]
    now = [o for o in options if o.wait_min == 0]
    baseline = min(now, key=lambda o: (o.duration_min, o.exposure_index))

    def evaluate_option(o: DepartureOption):
        extra = max(0.0, o.duration_min - baseline.duration_min)
        reduction = -_pct(o.exposure_index, baseline.exposure_index)
        cost = extra + A.WAIT_COST_WEIGHT * o.wait_min
        worth = k * reduction / 10.0
        ok = (o is baseline) or (
            o.wait_min <= max_wait_min and extra <= max_extra_min
            and reduction >= A.MIN_MEANINGFUL_REDUCTION_PCT and cost <= worth)
        return ok, extra, reduction, cost, worth

    accepted = [o for o in options if evaluate_option(o)[0]]
    rec = min(accepted, key=lambda o: (o.exposure_index, o.wait_min, o.duration_min))
    lowest = min(options, key=lambda o: (o.exposure_index, o.wait_min, o.duration_min))
    _, extra, reduction, cost, worth = evaluate_option(rec)

    if rec is baseline:
        kind = "stay"
    elif rec.wait_min == 0:
        kind = "route"
    elif rec.route_id == baseline.route_id:
        kind = "wait"
    else:
        kind = "wait_and_route"

    return Decision(
        recommended=rec, baseline=baseline, lowest=lowest, kind=kind,
        exposure_change_pct=-reduction if rec is not baseline else 0.0,
        arrival_change_min=round(rec.wait_min + (rec.duration_min - baseline.duration_min), 1),
        extra_travel_min=round(rec.duration_min - baseline.duration_min, 1), wait_min=rec.wait_min,
        accepted_cost_min=round(worth, 1), cost_min=round(cost, 1), sensitivity=sensitivity,
    )
