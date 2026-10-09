"""Every modelling assumption in one place.

These values are choices, not measurements. They are shown verbatim on the app's Method page (via
GET /meta), so changing a number here changes what users are told.
"""

from __future__ import annotations

# ------------------------------------------------------------------------------------------------
# Mode factors: relative inhaled dose per minute, walking = 1.0.
#
# Derived from US EPA Exposure Factors Handbook (2011, ch. 6) inhalation rates for adults:
# light activity ~0.72 m3/h, moderate ~1.56 m3/h, sedentary ~0.25 m3/h. Walking is treated as light
# activity and cycling as moderate. Motorised modes are sedentary; a closed car is further reduced
# by an assumed in-cabin/outdoor PM2.5 ratio of ~0.6 with windows up. AirGuard only ever compares
# options within one mode, so these factors scale the index but never decide a recommendation.
# ------------------------------------------------------------------------------------------------
MODE_FACTORS: dict[str, float] = {
    "walk": 1.0,
    "cycle": 2.0,
    "two_wheeler": 0.5,
    "car": 0.25,
}

MODE_LABELS: dict[str, str] = {
    "walk": "Walking",
    "cycle": "Cycling",
    "two_wheeler": "Two-wheeler",
    "car": "Car (windows up)",
}

# Routing profile used for each mode (OSRM / OpenRouteService profile family).
MODE_PROFILE: dict[str, str] = {
    "walk": "foot",
    "cycle": "bike",
    "two_wheeler": "car",
    "car": "car",
}

# ------------------------------------------------------------------------------------------------
# Risk bands for the average PM2.5 along a trip (µg/m³). Boundaries follow CPCB's PM2.5 AQI
# breakpoints. CPCB defines them for 24-hour averages; applying them to a trip average is our
# simplification, so the app calls this a "trip air level", not an AQI.
# ------------------------------------------------------------------------------------------------
RISK_BANDS: list[tuple[str, str, float]] = [
    # (key, label, upper bound inclusive)
    ("good", "Good", 30),
    ("satisfactory", "Satisfactory", 60),
    ("moderate", "Moderate", 90),
    ("poor", "Poor", 120),
    ("very_poor", "Very poor", 250),
    ("severe", "Severe", float("inf")),
]

# ------------------------------------------------------------------------------------------------
# Spatial interpolation and confidence
# ------------------------------------------------------------------------------------------------
SEGMENT_KM = 0.2             # route resolution
IDW_POWER = 2.0              # inverse-distance weighting exponent
IDW_NEIGHBOURS = 6           # stations used per point
IDW_MAX_KM = 25.0            # stations further than this are ignored (unless none is closer)
IDW_MIN_KM = 0.3             # distances are floored so a point on top of a station isn't infinite
SPATIAL_HALF_KM = 3.0        # spatial confidence = 1 / (1 + (d_nearest / SPATIAL_HALF_KM)^2)

# ------------------------------------------------------------------------------------------------
# Departure optimiser and decision layer
# ------------------------------------------------------------------------------------------------
DEPARTURE_STEP_MIN = 15
DEFAULT_WINDOW_H = 4
MAX_WINDOW_H = 6

# Extra minutes a user accepts for each 10% reduction in exposure. Sensitivity changes only the
# decision, never the exposure estimate.
MINUTES_PER_10PCT: dict[str, float] = {"normal": 4.0, "sensitive": 7.0, "high": 10.0}

SENSITIVITY_LABELS: dict[str, str] = {
    "normal": "Healthy adult",
    "sensitive": "Sensitive (asthma, older adult, pregnancy)",
    "high": "Highly sensitive (severe asthma, COPD, heart condition, small children)",
}

# Waiting before departure counts at half the cost of extra time on the road: you can wait indoors.
WAIT_COST_WEIGHT = 0.5

# Below this reduction the difference is within forecast noise; stay with the fastest option.
MIN_MEANINGFUL_REDUCTION_PCT = 5.0


def risk_band(pm25: float) -> tuple[str, str]:
    for key, label, upper in RISK_BANDS:
        if pm25 <= upper:
            return key, label
    return RISK_BANDS[-1][0], RISK_BANDS[-1][1]


def as_dict() -> dict:
    """Serialisable view for GET /meta."""
    return {
        "mode_factors": MODE_FACTORS,
        "mode_labels": MODE_LABELS,
        "risk_bands": [{"key": k, "label": lbl, "max_pm25": (None if u == float("inf") else u)}
                       for k, lbl, u in RISK_BANDS],
        "interpolation": {
            "segment_km": SEGMENT_KM, "idw_power": IDW_POWER, "idw_neighbours": IDW_NEIGHBOURS,
            "idw_max_km": IDW_MAX_KM, "spatial_half_km": SPATIAL_HALF_KM,
        },
        "decision": {
            "minutes_per_10pct": MINUTES_PER_10PCT, "sensitivity_labels": SENSITIVITY_LABELS,
            "wait_cost_weight": WAIT_COST_WEIGHT, "min_meaningful_reduction_pct": MIN_MEANINGFUL_REDUCTION_PCT,
            "departure_step_min": DEPARTURE_STEP_MIN, "default_window_h": DEFAULT_WINDOW_H,
            "max_window_h": MAX_WINDOW_H,
        },
    }
