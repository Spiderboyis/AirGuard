"""The exposure engine: pure functions, no network or database access.

field.py       space-time PM2.5 field from station forecasts (time interpolation + IDW)
segments.py    route polyline -> ~200 m segments
exposure.py    exposure index, risk level and confidence for one route and departure time
departure.py   15-minute departure grid and the sensitivity-aware decision rule
assumptions.py every modelling constant, shown verbatim in the app
"""
