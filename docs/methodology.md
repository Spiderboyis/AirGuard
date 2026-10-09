# Methodology

This page explains how AirGuard turns station data into route and departure advice, and states every
assumption. The constants quoted here live in [`backend/airguard/engine/assumptions.py`](../backend/airguard/engine/assumptions.py)
and are also served at `GET /meta`, which is what the app's Method page renders.

## 1. Station forecast

**Data.** Hourly PM2.5 from about 75 locations in Delhi NCR via OpenAQ v3: CPCB, DPCC, IMD, HSPCB and
UPPCB reference monitors, the US Embassy monitor (AirNow) and a few AirGradient sensors. Weather (2 m
temperature, humidity, 10 m wind, boundary-layer height) and the CAMS global PM2.5 model at each station
come from Open-Meteo. Active fires come from NASA FIRMS (VIIRS).

**Time alignment.** CPCB averages run on IST hours, which are UTC :30. Each hourly average is labelled
by its midpoint floored to the UTC hour, so every provider shares one hourly grid.

**Model.** One XGBoost regressor per horizon (0, 1, 3, 6, 12, 24 h), trained on all stations together
with a log-PM2.5 target. Features, built by one function for both training and serving:

| Group | Features |
| --- | --- |
| Station history | PM2.5 now and 1, 2, 3, 6, 12, 24 h ago; 3 h and 24 h means; 3 h change; 72 h ratio to CAMS |
| Neighbours | IDW mean of other stations reporting now (≤30 km); distance to the nearest; count within 15 km |
| CAMS | PM2.5 at issue time, at target time, and the max of the 3 h around target |
| Weather | Boundary-layer height and wind at issue and target time; wind u/v, humidity, temperature at target |
| Fires | VIIRS detections 20–400 km away in the upwind 45° sector over the two complete days before |
| Calendar / place | Target hour of day (IST, sin/cos), day of week, horizon, station lat/lon, monitor vs low-cost |

**Delayed feeds.** CPCB data on OpenAQ sometimes arrives hours or days late. When a station's newest
reading is older than 3 hours, its own history features are blanked and the model leans on CAMS, weather
and neighbours. Training blanks the same features on 25% of rows (100% for the "now" model), so this
case is learned rather than improvised. The app marks such stations as *estimated*.

**Backtest.** Time-based split: train on everything up to the calibration week (with a 24 h gap), set
the 80% interval on the calibration week (10th and 90th percentiles of actual ÷ predicted, i.e. split
conformal), and report on the final 14 days. Baselines:

1. **Persistence**: the last reading.
2. **Hour-of-day mean** for the station, from the training period.
3. **Raw CAMS** forecast at the station.

Metrics (MAE, RMSE, interval coverage and width) are stored per horizon and mode in `eval_metrics` and
shown on the Evidence page.

## 2. From stations to a route

Routes come from OSRM's foot, bike and car profiles (FOSSGIS servers). If OSRM returns fewer than three
distinct routes, AirGuard also asks for routes through a point 0.8–3 km to either side of the midpoint,
keeping those that are at least 25% different and at most 60% slower than the fastest.

Each route is cut into **200 m segments**. A segment's travel time is its share of the route's distance
times the route duration; its PM2.5 is taken at the time you would reach its midpoint:

1. each station's forecast series is linearly interpolated in time;
2. the six nearest stations within 25 km are blended by **inverse-distance weighting** (power 2, distances
   floored at 0.3 km). If none is within 25 km, the six nearest are used anyway and confidence is low.

**Confidence** for a segment is the geometric mean of

- spatial: `1 / (1 + (d_nearest / 3 km)²)`, and
- interval: `1 / (1 + (high − low) / predicted)`.

A route's confidence is the time-weighted mean over its segments.

## 3. Exposure index

```
exposure index = Σ_i  C_i × t_i × m        (µg·h/m³)
```

`C_i` is segment PM2.5, `t_i` hours on the segment, `m` the mode factor. The low and high indices use the
forecast range in place of `C_i`.

| Mode | Factor | Basis |
| --- | --- | --- |
| Walk | 1.0 | Light activity (US EPA Exposure Factors Handbook 2011, ch. 6: ~0.72 m³/h) |
| Cycle | 2.0 | Moderate activity (~1.56 m³/h, about 2.2× light) |
| Two-wheeler | 0.5 | Seated (~0.25 m³/h), open to traffic |
| Car | 0.25 | Seated, windows up, assumed in-cabin/outdoor ratio ~0.6 |

These are assumptions. The app compares options **within one mode only**, so the factor scales the
index but never decides a recommendation.

**Trip air level.** The trip's mean PM2.5 is labelled with CPCB's PM2.5 bands (Good ≤30, Satisfactory ≤60,
Moderate ≤90, Poor ≤120, Very poor ≤250, Severe above). CPCB defines these for 24-hour averages; applying
them to a trip mean is a simplification, so the app calls it an air level, not an AQI.

### A route checked by hand

`tests/test_engine.py::test_hand_checked_route`: stations A (100 µg/m³) and B (200 µg/m³) on the same
latitude, B ~2.93 km east of A. A 0.6 km walk due east from A takes 12 minutes, so three segments of
4 minutes with midpoints 0.1, 0.3 and 0.5 km from A.

| Segment | d(A) used | d(B) | w(A) = 1/d² | w(B) | PM2.5 | × 4/60 h |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.3 (floored) | 2.83 | 11.11 | 0.125 | 101.1 | 6.74 |
| 2 | 0.3 | 2.63 | 11.11 | 0.145 | 101.3 | 6.75 |
| 3 | 0.5 | 2.43 | 4.00 | 0.169 | 104.1 | 6.94 |

Exposure index ≈ **20.4** µg·h/m³, which the test asserts to 0.1%.

## 4. Departure optimiser and decision

Every route is scored for departures every 15 minutes across the window (default 4 h, max 6 h). These
are scenario evaluations on an interpolated forecast, not 15-minute forecasts.

The **baseline** is the fastest route leaving now. Any other option is accepted only if

```
cost  = extra travel minutes + 0.5 × minutes waited
worth = k × reduction% / 10           (k = 4 normal, 7 sensitive, 10 highly sensitive)
cost ≤ worth,  extra ≤ max_extra_min,  wait ≤ max_wait_min,  reduction ≥ 5%
```

and the recommendation is the lowest-exposure accepted option. Waiting counts half because people can
wait indoors. A sensitive user accepts 7 minutes for every 10% less exposure, so a 30-minute wait (cost
15) needs at least a 22% reduction. Sensitivity changes only this rule; the exposure estimate is the
same for everyone.

## 5. The assistant

Built with the Strands Agents SDK. With a trip on screen it gets two tools (`get_trip_result`,
`now_ist`); otherwise it gets `geocode`, `best_departure_time`, `score_routes`, `get_forecast` and
`now_ist`. Small local models choose far more reliably from a short list.

Every tool call is recorded (name, input, output, duration) and streamed to the UI. Before an answer is
shown, `agent/guard.py` extracts every number and clock time and checks each against the tool outputs
and the user's message (allowing rounding, absolute values and fractions written as percentages). If
anything can't be traced, or a trip question ends on a failed tool call, the answer is replaced by a
deterministic explanation of the saved analysis, and the UI says so.

## Limits

- Sparse monitors: most of a route is interpolated; roadside concentrations can exceed any nearby station.
- Travel times are free-flow OSRM estimates without live traffic.
- Forecast horizon 24 h; departures up to 6 h ahead from now (no scheduled future trips in v1).
- The exposure index is a model estimate under stated assumptions, not a measured dose.
- General guidance only, not medical advice.
