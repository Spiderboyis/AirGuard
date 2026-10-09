# Demo script (2 to 3 minutes)

1. Open the planner on the frozen snapshot (`?offline=1` if the API is down, or tick Demo mode after `python scripts/snapshot.py`).
2. One person, one trip: a student cycles from Hauz Khas to DU North Campus.
3. Show two or three routes. Read duration, exposure index, AirGuard level, and data reliability. The colour legend is text as well as colour.
4. Read the departure sentence. It is computed by the engine: extra minutes against the change in exposure index. Say that the 15-minute steps are interpolated between five forecast horizons.
5. Ask the scripted question. Open "Tools used" and show that the numbers in the answer come from the tool output.
6. Open Evaluation. Quote MAE against persistence and the hour-of-day mean. If the model loses at a horizon, say so. If the version contains `synthetic`, say these are local development numbers, not the Delhi backtest.
7. One line on the stack: Strands Agents SDK, and, if deployed, Lambda, API Gateway, EventBridge, S3, and Bedrock. A local run still uses Strands.
8. Close with the limit: this is an exposure index under stated assumptions, not a measured dose and not medical advice.

Quote only numbers printed by `docs/headline.json` or shown on screen. Do not invent a percentage.
