# AirGuard: Implementation Guide (AWS Hackathon, Air Track)

Oct 8, 2026 · @Harshit

## Overview

AirGuard tells a Delhi commuter which route to take and when to leave to breathe less pollution, using a forecast with an honest uncertainty estimate and an AI agent that explains the trade-off.

- **Thesis to prove:** the same trip, a few minutes longer or later, cuts predicted PM2.5 exposure by a measurable amount. Show it on one real Delhi route with one headline number ("+X minutes, −Y% exposure"), computed by your own script from a frozen forecast snapshot, not guessed. The station-level forecast is validated separately (MAE and RMSE on held-out data); the route-level difference is an estimate under stated assumptions, not a measured reduction in what a person inhaled.
- **Problem:** AQI apps show current readings on a map. They don't change what a person does on a bad-air day.
- **Users:** asthmatic commuters, cyclists, and parents walking children to school.
- **Track:** Air, under the "Pollution exposure" theme.
- **Eligibility:** Strands Agents SDK is an AWS open source tool, and the backend and frontend are deployed on AWS. Either one qualifies; having both is safer.
- **What wins:** a deployed URL that works during judging, evidence (a backtest with error numbers), visible agent tool calls, and a rehearsed demo. The idea is shared with other teams; execution is not.

## Constraints and assumptions

The plan is built for zero spend, three days, and two people who each ship about twice a normal developer's output with AI help.

- **Cost target, near zero:** use only free tiers and AWS free credits. Stay on the AWS free plan and do not upgrade to a paid plan. Set an AWS Budgets alert at $1 on day one. It warns you but does not stop spending, so check the Billing page daily, keep resources minimal, and shut everything down after judging. The plan is designed to minimise cost, not to guarantee zero.
- **Time:** 3 days, with a feature freeze at midday on Day 3 and submission at least a few hours before the deadline.
- **Team:** Person A owns data, ML, routing, and evaluation (correctness of the numbers). Person B owns the agent, frontend, AWS deployment, and demo (what judges see and whether it stays up).
- **Rules from the hackathon page:** the project must use at least one AWS open source tool or be deployed on AWS. Other tools are allowed.
- **Data granularity:** most Indian station data is hourly. Forecast at five horizons (+1h, +3h, +6h, +12h, +24h), not every hour and not every 15 minutes; the engine interpolates between those points.
- **Open items to check before coding:** the judging criteria and prize list on the hackathon page, your OpenAQ key and how many Delhi stations reported recently, and whether your AWS credits cover the LLM you pick.

**Departure scope in v1.** AirGuard compares leaving now with waiting and leaving later, up to 4 hours ahead by default (the API accepts up to 6), evaluated every 15 minutes. It does not plan a trip for a specific scheduled clock time such as "tomorrow 8 AM"; say so in the pitch if asked. Supporting scheduled departures would mean passing a start offset through the API, the agent tools, and the optimizer's baseline.

**Local first, deploy only if needed.** Build and run everything on your laptop first: the API with `uvicorn`, the frontend with `npm run dev`, Supabase's free hosted database, and Ollama for the agent. Decide at the Day 2 gate whether to deploy to AWS. Eligibility should hold either way, because the hackathon page you shared lists Strands Agents SDK as an AWS open source tool (confirm that wording on the official page before relying on a local-only submission; see Appendix J); deploying adds a public URL that judges can open. Appendix M lists the local equivalent of every deploy step and the three small code changes local mode needs.

## System architecture

AirGuard has two paths: a trip request path (frontend, one Lambda API, Supabase, Bedrock, OpenRouteService) and an hourly pipeline that keeps forecasts fresh in Supabase.

&#91;embedded content: architecture · trip path and hourly pipeline\]

The frontend only talks to the API; the API reads forecasts from Supabase, asks OpenRouteService for routes, and uses Bedrock for the agent, while the hourly Lambda writes new forecasts using models stored in S3.

**Design principle:** numbers come from deterministic code (forecast, interpolation, exposure engine). The LLM only picks which tools to call and explains their output, so it never invents a value.

**Data flow for one trip:**

1. The user enters origin, destination, mode, and time in the frontend.
2. The API fetches 2 to 3 candidate routes (cached when possible).
3. The engine interpolates station forecasts along each route and computes exposure index and confidence.
4. The departure optimizer repeats this for later start times.
5. The agent calls the same functions as tools and returns a plain-language recommendation plus the tool-call trace.

## Tech stack (all free or covered by AWS credits)

Every layer below has a free option; the right column says what to use instead if the first choice costs money or breaks.

| Layer | Use | Free fallback or note |
| --- | --- | --- |
| Frontend | Next.js + Tailwind | Amplify Hosting; Vercel free tier as backup |
| Map | MapLibre GL JS | Free tiles from OpenFreeMap or MapTiler free tier. Don't hammer OSM's own tile server. |
| Geocoding | Nominatim or Photon | About 1 request/second. Cache results and hardcode a few demo places. |
| Database | Supabase Postgres + PostGIS | Free plan. Neon is a backup. Free projects pause when inactive, so open yours the day before judging. |
| Auth | Supabase Auth | Pick one auth system only (not Cognito as well) |
| Backend | FastAPI (Python) on Lambda + API Gateway (via Mangum) | Pay-per-use, free tier is generous. Avoid always-on App Runner. |
| Air data | OpenAQ v3 (free API key) | Open-Meteo Air Quality API as a baseline feature and fallback |
| Weather | Open-Meteo | Free, no key: wind, humidity, temperature, boundary-layer height |
| Fires | NASA FIRMS (free key) | Upwind fire counts; relevant to Delhi in October |
| Routing | OpenRouteService free API key (alternative routes) | Or precompute demo routes and cache them in Supabase. Self-hosting OSRM needs an always-on server, so skip it. |
| ML | XGBoost or LightGBM, scikit-learn | Train in a notebook, store the model in S3 |
| Agent | Strands Agents SDK | Your qualifying AWS open source tool |
| LLM | Amazon Nova via Bedrock (first-party) | Use us-east-1 for the Bedrock demo; verify model access and the inference mode in the Bedrock console, and verify credits cover it. Third-party Marketplace models may not be covered. Ollama in dev. |
| Scheduler | EventBridge → Lambda | Hourly ingestion and forecast refresh |
| Alerts | SNS, email only (stretch goal) | SMS costs money |
| Secrets | SSM Parameter Store (standard tier) | Secrets Manager charges per secret |
| Logs | CloudWatch | Free tier is enough |

**Avoid:** NAT Gateways and VPC setups (hourly charges), Route 53 or custom domains, SNS SMS, always-on EC2 or App Runner, and any SageMaker endpoint.

## Data sources and database schema

Four free sources feed one Postgres database with PostGIS; everything else (forecasts, routes, evaluation) is derived from it.

| Source | What it gives you | Notes |
| --- | --- | --- |
| OpenAQ v3 | Station PM2.5 and other pollutants, mostly hourly | Needs a free API key. Check how many Delhi stations reported in the last 7 days. |
| Open-Meteo | Wind, humidity, temperature, boundary-layer height; also an air quality forecast | No key. Its air quality forecast is an optional extra baseline that this guide does not implement (coarse over India). |
| NASA FIRMS | Active fire detections (stubble burning) | Free key. Count fires upwind within a radius. |
| OpenRouteService | 2 to 3 alternative routes with geometry and duration | Free key with daily limits. Cache every response. |

Create this schema in Supabase (enable the `postgis` extension first):

```sql
create extension if not exists postgis;

create table stations (
  id text primary key,
  name text,
  geom geography(Point, 4326) not null,
  source text default 'openaq'
);

create table measurements (
  station_id text references stations(id),
  pollutant text not null,
  value double precision,
  unit text,
  ts timestamptz not null,
  primary key (station_id, pollutant, ts)
);
create index on measurements (ts desc);

create table weather (
  ts timestamptz not null,
  station_id text references stations(id),
  wind_speed double precision,
  wind_dir double precision,
  humidity double precision,
  temp double precision,
  blh double precision,
  fires_upwind integer,
  primary key (station_id, ts)
);

create table forecasts (
  station_id text references stations(id),
  horizon_h integer not null,
  target_ts timestamptz not null,
  pm25_pred double precision,
  pm25_low double precision,
  pm25_high double precision,
  model_version text,
  generated_at timestamptz default now(),
  primary key (station_id, horizon_h, target_ts, model_version)
);

create table eval_metrics (
  model_version text,
  horizon_h integer,
  mae double precision,
  rmse double precision,
  baseline_persistence_mae double precision,
  baseline_hourly_mean_mae double precision,
  n_samples integer,
  primary key (model_version, horizon_h)
);

create table route_cache (
  key text primary key,
  response jsonb not null,
  created_at timestamptz default now()
);
```

Use the Supabase service key only in the backend. Appendix C adds latitude, longitude, and sensor columns to `stations`, and Appendix D adds a `forecasts_latest` table and turns on row-level security. There is no user table in v1: the profile lives in browser state, and the frontend needs no database key.

## Forecasting design

Train one global XGBoost model per forecast horizon, using data pooled across eligible Delhi stations, with station-local features and neighbouring-station observations, prove it beats two simple baselines on a time-based holdout, and report the error honestly even where it doesn't.

**Horizons:** +1h, +3h, +6h, +12h, +24h (hourly data).

**Features per station and hour:**

- Lagged PM2.5 at 1h, 3h, 6h, and 24h, plus rolling means
- Hour of day, day of week
- Wind speed and direction, humidity, temperature, boundary-layer height (Open-Meteo)
- Count of FIRMS fire detections upwind within a radius (kept only if the ablation in Appendix D shows it helps)
- PM2.5 at the nearest neighbouring stations

**Baselines to beat:**

1. Persistence: next value equals the last value.
2. Hour-of-day average for that station.
3. Optional extension, not implemented in this guide: Open-Meteo's own air quality forecast (coarse over India).

**Backtest:** split by time (train on earlier weeks, test on the latest week or two), never randomly. For each horizon store MAE and RMSE for the model and for each baseline in `eval_metrics`. This feeds the evaluation page in the app and is your main credibility asset.

**Uncertainty:** train quantile models (for example 10th and 90th percentile) or use residual quantiles from the backtest, and store them as `pm25_low` and `pm25_high`.

**Backfill:** pull as much OpenAQ history as the API allows for Delhi stations on Day 1, so you have enough data to train on Day 2. If history is thin, say so in the doc and the pitch, and reduce the number of horizons.

**Serving:** save the model files to S3 and load them in the Lambda at cold start. The hourly EventBridge job fetches new data, builds features, predicts, and writes to `forecasts`. Don't run SageMaker endpoints.

**Spatial step:** forecasts are per station. Interpolate to points along a route with inverse-distance weighting, and attach a confidence value that falls as distance to the nearest station grows.

## Exposure and routing engine

The engine is a pure Python module that turns candidate routes plus forecasts into an exposure index per route and a best departure time. It is the most important code in the project, so keep it free of network calls and cover it with unit tests.

**Steps for one trip:**

1. Request 2 to 3 alternative routes (OpenRouteService), or load cached ones.
2. Split each route into segments of about 200 m, each with an expected arrival time from the route's duration and the chosen mode's speed.
3. For each segment, take the interpolated PM2.5 forecast for its arrival hour (inverse-distance weighting across stations).
4. Compute exposure index per segment and sum:

```latex
\text{exposure index} = \sum_{i} C_i \cdot t_i \cdot m
```

Here C\_i is the interpolated PM2.5 on segment i (µg/m³), t\_i is the time spent on it, and m is the mode factor.

5. Return per route: duration, distance, exposure index, a risk level, a confidence value, and the per-segment breakdown.

**Mode factors are assumptions.** Walking is the baseline of 1.0. Cycling should be higher because of greater breathing rate; a closed car should be lower because of in-vehicle filtration. Pick the values, write them in the code and in the UI as stated assumptions, and don't present them as measured.

**Compare options within one mode.** Route and departure comparisons within the same mode are defensible. Comparing exposure-index values across walking, cycling, and driving rests on unvalidated factors, so the app compares one mode at a time, and the pitch should not say "cycling exposes you X% more than driving" or draw health conclusions from the factors.

**Confidence:** combine distance to the nearest station and the width of the forecast interval. Show it next to every exposure number.

**Departure optimizer (the headline feature):** repeat the calculation for departures every 15 minutes across the next 4 hours by default (up to 6) (the model forecasts at five horizons between +1 and +24 hours and the engine interpolates between those points, so these are scenario evaluations, not 15-minute forecasts), and return the option with the best trade-off between added waiting time and exposure index reduction. Output examples such as "leave 40 minutes later: exposure index −Y%, arrival +X min", with real numbers from the engine.

**Sensitivity changes the choice, not the estimate.** The exposure index never depends on who is travelling. A decision layer picks the recommended option afterwards, using three inputs from the user: sensitivity (normal, sensitive, or high), the most extra minutes they will accept, and the longest they will wait. Sensitivity sets how many extra minutes the user will accept for each 10% reduction in exposure: 4 for normal, 7 for sensitive, and 10 for high (illustrative defaults; justify your own). An option that adds 10 minutes must therefore cut exposure by about 25% for a normal user, 14% for a sensitive user, and 10% for a very sensitive user. The recommendation is the lowest-exposure option that passes this rule and both limits. What to tell a judge: sensitivity does not change the pollution estimate, it changes how strongly the decision engine trades time for lower exposure.

**Tests to write on Day 1 and 2:**

- A route through a uniform field gives exposure index equal to concentration × time × m.
- A single hot station near one route raises that route's exposure index and lowers its confidence elsewhere.
- Moving departure into a lower-forecast hour lowers exposure index.
- A hand-checked sample route matches a calculation done in a spreadsheet.

## Agent design (Strands)

The agent chooses which tools to call and explains the results; every number comes from a tool. This is the part that qualifies you under the AWS open source rule, so make the tool calls real and visible.

**Tools** (each a thin wrapper over one backend function with typed inputs and outputs):

| Tool | Purpose |
| --- | --- |
| `geocode(place)` | Turn a place name into coordinates (cached, with a few hardcoded demo places) |
| `get_forecast(location, horizon_h)` | Forecast PM2.5 with low and high bounds and confidence |
| `score_routes(origin, dest, mode)` | Routes with duration, exposure index, risk, confidence |
| `best_departure(origin, dest, mode, window_h)` | Best departure time and the trade-off against waiting |
| `get_user_profile(user_id)` | Sensitivity and usual travel mode |
| `create_alert(user_id, rule)` | Email alert via SNS for a bad commute window |

**System prompt rules:**

- Call a tool for every number; never estimate or invent values.
- State uncertainty: report confidence and the forecast range.
- Recommend the lowest-exposure option that fits the user's stated time tolerance.
- Give general guidance only, not medical advice; suggest a doctor for health questions.
- If a tool fails or data is stale, say so plainly.

**Model:** Amazon Nova via Bedrock for the deployed demo, if your credits cover it (check in the Bedrock console). Use Ollama in development to avoid spending credits.

**UI:** show each tool call and its result in the chat panel as it happens, so judges see the agent working.

**Fallbacks and cost protection:**

- Rate-limit `/agent/chat` per IP so a judge cannot burn your credits.
- Cache agent answers for your demo trips.
- If Bedrock fails, serve the cached answer and label it as cached.
- If credits don't cover any hosted model, the agent can still run through Strands with a free or local model; you keep the qualifying open source tool but lose the Bedrock mention. Appendix G implements this tool set with three changes: best\_departure becomes best\_departure\_time, a now\_ist tool replaces get\_user\_profile (the profile arrives in each request), and create\_alert becomes an optional send\_email\_summary. A new get\_trip\_result tool lets the agent explain the trip the user already analyzed from a saved result, without recomputing it or making slow network calls.

## API contracts

Agree these shapes in the first two hours and put them in a `contracts/` folder as OpenAPI or JSON schema. Then Person A and Person B can build against mocks in parallel and swap in the real services later.

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | GET | Liveness check plus data freshness (last ingestion time) |
| `/forecast` | GET | Forecast for a point and horizon |
| `/routes/score` | POST | Candidate routes with exposure index, risk, and confidence |
| `/departure/best` | POST | Best departure time within a window |
| `/agent/chat` | POST | Agent conversation, returns the answer and tool-call trace |
| `/eval` | GET | Backtest metrics per horizon |

**`POST /routes/score`**

```json
{
  "origin": {"lat": 28.6139, "lon": 77.2090},
  "destination": {"lat": 28.5355, "lon": 77.3910},
  "mode": "cycle",
  "sensitivity": "sensitive"
}
```

Response:

```json
{
  "routes": [
    {
      "id": "r1",
      "duration_min": 42,
      "distance_km": 11.8,
      "exposure_index": 82.0,
      "risk": "high",
      "confidence": 0.74,
      "geometry": [[77.209, 28.614], [77.210, 28.613]],
      "segments": [
        {"lat": 28.605, "lon": 77.215, "pm25": 96.4, "minutes": 2.1, "line": [[77.21, 28.61], [77.22, 28.60]]}
      ]
    }
  ],
  "data_freshness_min": 38
}
```

The numbers above are placeholders to show the shape only; the real values come from the engine.

**`POST /departure/best`**

```json
{
  "origin": {"lat": 28.6139, "lon": 77.2090},
  "destination": {"lat": 28.5355, "lon": 77.3910},
  "mode": "cycle",
  "window_h": 4,
  "max_extra_min": 15,
  "max_wait_min": 120,
  "sensitivity": "sensitive"
}
```

Response: a list of `{wait_min, route_id, duration_min, exposure_index, confidence}` for each 15-minute step, plus `recommended` with the chosen entry and `delta` against the fastest route leaving now (`exposure_index_pct`, `arrival_min`).

Both trip endpoints also take `sensitivity` (`normal`, `sensitive`, or `high`), `max_extra_min`, and `max_wait_min`. They feed the decision layer only; the exposure numbers are the same for every sensitivity.

**`POST /agent/chat`**

Request: `{"message": "...", "profile": {"sensitivity": "...", "mode": "..."}, "history": [], "demo": false}`. Response: `{"answer": "...", "tool_calls": [{"name": "score_routes", "input": {...}, "output": {...}}], "cached": false}`.

The planner calls POST /trips/analyze (routes and departure advice in one call, returning a trip\_id), and the agent reads that saved result instead of recomputing the trip. All responses use the same error shape: `{"error": {"code": "...", "message": "..."}}`. Validate coordinates server-side, and keep Supabase service keys out of the frontend.

## Low-cost AWS deployment

This whole section is optional until you decide to deploy (the plan is local first; see Appendix M). When you do, deploy a hello-world version first and redeploy often; most hackathon time lost on AWS comes from permissions and region problems found too late.

**Steps:**

1. Create the AWS account on the free plan. Set an AWS Budgets alert at $1. Do not upgrade to a paid plan.
2. Use the us-east-1 region for everything. In the Bedrock console there, request access to the model you plan to use, check which inference mode it offers (in-region, geo, or global), and confirm that your credits apply to it.
3. Install the SAM CLI and write a `template.yaml` for the API, agent, and hourly ingestion Lambdas (one container image, see Appendix F), an API Gateway HTTP API, the hourly EventBridge rule, and an S3 bucket for model artifacts.
4. Store keys (OpenAQ, FIRMS, OpenRouteService, Supabase service key) in SSM Parameter Store, and give the Lambda read access only to those parameters.
5. Deploy the backend, then call `/health` from your laptop and from the frontend.
6. Connect the frontend repo to Amplify Hosting (or Vercel as a backup) and point it at the API Gateway URL.
7. Create an SNS topic with your email as a subscriber for alerts.
8. Add an IAM role for Bedrock invoke on the backend Lambda, scoped to the one model.
9. Test the full path on the deployed stack with the demo trip every day, not only on Day 3.

**Free-tier traps:**

- Supabase Free pauses inactive projects. Open it the day before judging and keep cached data as a fallback.
- Lambda cold starts with a large ML library can be slow. Keep the model small, warm the function before the demo, and cache the demo trips.
- Free APIs rate-limit. Cache every response and precompute the demo routes.
- A public agent endpoint can burn credits. Add rate limits and cached answers.
- Avoid NAT Gateways, always-on instances, Route 53, and SMS. They are the usual sources of surprise charges.

**After judging:** delete the stack (`sam delete`), the S3 bucket, and the SNS topic, and check the billing page.

## Repo layout and work split

One repo, one folder per module and one owner per folder, so two people (each running several AI agents) don't collide in merges.

```text
airguard/
  contracts/   OpenAPI + JSON schemas, written first
  ingestion/   OpenAQ, Open-Meteo, FIRMS clients; Lambda handlers; backfill script
  ml/          features, training, backtest, model export
  engine/      interpolation, exposure, departure optimizer + tests (pure Python)
  api/         FastAPI app, Mangum handler
  agent/       Strands agent, tools, prompts
  frontend/    Next.js app, MapLibre map, chat panel, evaluation page
  infra/       SAM template, deploy scripts, env examples
  docs/        README, architecture diagram, demo script
  common/      shared config, database and geometry helpers
  scripts/     backfill and demo-snapshot scripts
  tests/       pytest tests
```

| Owner | Folders | Responsible for |
| --- | --- | --- |
| Person A | `ingestion`, `ml`, `engine` | Data, forecast, backtest, exposure math, correctness |
| Person B | `api`, `agent`, `frontend`, `infra`, `docs` | Agent, UI, AWS deployment, demo, stability |
| Both | `contracts` | Agreed together before any feature code |

**Working rules with AI agents:**

- Treat yourselves as tech leads: assign work to agents per folder, review diffs, and integrate daily.
- Write the contract first; every agent codes against it.
- Have one agent write tests for the exposure logic and a second review the calculation independently.
- Commit small and often, merge to `main` at least twice a day, and keep `main` deployable.

## 3-day implementation plan

The plan is built around three gates: a working vertical slice at the end of Day 1, all features working at the end of Day 2 (locally, or deployed if you chose to), and a feature freeze at midday on Day 3.

&#91;embedded content: 3-day plan · 2 people, 3 gates\]

Each person owns one lane; the gates are checked together, and nothing new is started after the freeze.

**Timeboxes**

- **Hours 0 to 3:** write the contracts, create the repo and Supabase schema, get the API running locally, and check Delhi station coverage in OpenAQ. If you plan to deploy, also deploy hello-world to AWS and confirm Bedrock access and credit coverage.
- **End of Day 1:** one real Delhi trip runs end to end, locally or on the deployed stack, even if the interface is rough.
- **Day 2 morning:** real forecast with a first backtest, route scoring, and the agent's tools wired to real endpoints.
- **Day 2 afternoon:** departure optimizer, profile personalization, and the evaluation page (email alerts are a stretch goal).
- **Day 3 before midday:** bug bash with a "break it" agent, fallbacks tested, demo trips cached.
- **Day 3 midday:** feature freeze. The afternoon is only the demo video, a backup recording, the README, and submission.

**Stretch goals, only if the Day 2 gate passes with time to spare:** a city-wide forecast grid with live map updates, a school-run mode using the same engine, and a second city. Skip them if anything on the core path is unstable.

## Testing, reliability, and security

Judges forgive a missing feature more readily than a crash, so spend the last day on tests, fallbacks, and a bug bash instead of new features.

**Tests**

- Unit tests for interpolation, exposure index calculation, and the departure optimizer.
- Contract tests: every endpoint's response validates against the schema in `contracts/`.
- One end-to-end test for the demo trip against the deployed stack.
- A "break it" pass, ideally by a separate AI agent: invalid coordinates, a trip outside Delhi, a station with no recent data, API timeouts, Bedrock errors, an empty route list.

**Reliability**

- Cache the last good readings, forecasts, and routes in Supabase and show a "data is N minutes old" banner.
- Precompute and cache your demo trips so the demo never depends on a live free API.
- Serve cached agent answers when Bedrock or a model call fails, and label them as cached.
- Open Supabase the day before judging so the project is not paused.
- Record a backup demo video before the final submission.

**Security**

- Keep all keys in SSM Parameter Store; none in the frontend or the repo. Commit only an `.env.example`.
- Use the Supabase service key only in the backend.
- Limit CORS to your frontend's domain.
- Rate-limit `/agent/chat` per IP.
- Validate every input server-side (coordinate ranges, mode values, time windows).
- Show a short disclaimer in the app: guidance only, not medical advice.

## Risks and prepared answers

The biggest threat is Delhi's sparse sensor network: say so first, show confidence, and let honesty work for you.

| Risk | Likelihood and impact | Mitigation |
| --- | --- | --- |
| Few stations make route-level exposure mostly interpolation | High, hits credibility | Show confidence scores and forecast ranges; state the limitation in the pitch |
| AWS permission or region problems | Medium, can block a day | Deploy hello-world in the first two hours; test Bedrock access immediately |
| Credits don't cover the chosen LLM | Medium | Use Amazon Nova; keep a Strands + free or local model fallback and cached answers |
| Free API limits or outages during the demo | Medium | Cache everything; precompute demo trips |
| Supabase project paused | Medium, easy to prevent | Open it the day before; keep a cached fallback |
| Forecast doesn't beat baselines at some horizons | Medium | Report it honestly and lead with the horizons where it does |
| Scope creep in the last day | High | Feature freeze at midday on Day 3 |
| Lambda cold start during the demo | Low to medium | Warm the function before the demo; keep the model small |

**Questions judges are likely to ask, and your answers:**

- *How do you know Route B is cleaner than Route A?* We forecast station PM2.5, interpolate along each route, and report confidence. Where stations are far from a route, confidence drops and we say so.
- *How accurate is the forecast?* Quote your backtest: MAE and RMSE per horizon against persistence and hour-of-day baselines.
- *Why an agent instead of a form?* It personalizes by profile, calls the forecast, routing, and departure tools, and explains trade-offs in plain language; the numbers still come from tools.
- *Why AWS?* Strands is the agent framework, Lambda and API Gateway host the backend, EventBridge runs the hourly job, S3 stores models, SNS sends alerts, and Bedrock runs the model.
- *What about health claims?* The app gives exposure guidance based on stated assumptions, not medical advice.

## Demo script and submission checklist

Open with a person and one real Delhi trip, show the agent working, close with evidence, and keep the whole demo to two or three minutes.

**Demo script (2 to 3 minutes)**

1. A named person and a real route: "Riya cycles to college in Delhi at 8 AM."
2. Show 2 to 3 routes on the map with their exposure and confidence.
3. Ask the agent which to take; show it calling tools and the reasoning it returns.
4. Show the departure-time result: "leave later, same trip, lower exposure", with the real numbers from your engine.
5. Show the evaluation page: forecast error per horizon against the baselines.
6. One line on AWS: Strands Agents SDK, Lambda and API Gateway, EventBridge, S3, SNS, and Bedrock.
7. Close with what is next: school-run mode, a public API, more cities, and a licensed or self-hosted weather source in place of Open-Meteo's free non-commercial tier.

**Submission checklist**

- [ ] Live URL works on a fresh browser and on mobile
- [ ] Demo trip is cached and loads quickly
- [ ] Demo video recorded (2 to 3 minutes) plus a backup recording
- [ ] README with problem, architecture diagram, setup steps, screenshots, and the headline number
- [ ] Evaluation page shows real backtest numbers and the baselines
- [ ] Agent's tool calls are visible in the UI
- [ ] Assumptions (mode factors, interpolation, confidence) documented in the app
- [ ] Strands Agents SDK use stated clearly, plus the AWS deployment (both rules covered)
- [ ] Each judging criterion mapped to a line in the submission text
- [ ] AWS Budgets alert set; billing page checked
- [ ] Supabase project open and active
- [ ] Submitted at least a few hours before the deadline
- [ ] After judging: stack deleted, billing checked

## Build kit (appendices)

The appendices below turn the plan into build instructions: accounts, commands, code, and checks. The code is starter code checked against the official docs I could open, but it has not been run in your environment, so run each piece once and fix what differs. Appendix K lists what to verify first.

## Appendix A: Accounts, keys, and environment variables

Sign up for everything below on Day 1, before writing code. Use `us-east-1` for AWS and pick the US East region for Supabase, so Lambda-to-database calls stay fast and the Bedrock demo uses a region AWS documents for the model (verify access and inference mode in the console; see Appendix K).

| Service | Used for | Where to get it | Variables | Limits to know |
| --- | --- | --- | --- | --- |
| AWS (free plan) | Lambda, API Gateway, EventBridge, S3, SNS, SSM, Bedrock | aws.amazon.com/free | `aws configure` credentials, region `us-east-1` | Budgets alert at $1; stay on the free plan |
| Supabase | Postgres, PostGIS | supabase.com, new project | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (backend only) | Free projects pause when inactive |
| OpenAQ | Station PM2.5 | explore.openaq.org/register, then create an API key | `OPENAQ_API_KEY` | 60 requests/minute and 2,000/hour; a 429 means wait; repeated excess can lead to a ban; source attribution required |
| NASA FIRMS | Fire detections | firms.modaps.eosdis.nasa.gov/api/map\_key/ (email only, no approval) | `FIRMS_MAP_KEY` | Free |
| OpenRouteService | Route alternatives | openrouteservice.org, sign up for a token | `ORS_API_KEY` | Alternative routes only work for routes under 100 km; check your daily quota in the dashboard |
| Open-Meteo | Weather and an air quality baseline | No key | none | Free for non-commercial use; you must credit Open-Meteo and CAMS; cache everything; a commercial product would need a licence or self-hosting |
| Map tiles | Basemap | OpenFreeMap (no key) or a MapTiler free key | `NEXT_PUBLIC_MAP_STYLE_URL` | Don't hammer OpenStreetMap's own tile server |
| Nominatim | Geocoding | No key | none | Send a descriptive User-Agent; about 1 request/second |
| Ollama | Free local LLM for development | ollama.com | `OLLAMA_HOST`, `OLLAMA_MODEL` | Pick a model that supports tool calling |
| GitHub | Repo; Amplify deploys from it | github.com | none | Free |

**Backend `.env`** (never commit it; commit a `.env.example` with empty values):

```text
LOCAL=1
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=
OPENAQ_API_KEY=
FIRMS_MAP_KEY=
ORS_API_KEY=
CONTACT_EMAIL=you@example.com   # sent to Nominatim in the User-Agent, as its usage policy requires
MODEL_BUCKET=airguard-models-<your-suffix>
LLM_BACKEND=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1
BEDROCK_MODEL_ID=amazon.nova-2-lite-v1:0
AWS_REGION=us-east-1
ALLOWED_ORIGINS=http://localhost:3000
```

**Frontend `frontend/.env.local`:**

```text
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_MAP_STYLE_URL=https://tiles.openfreemap.org/styles/liberty
```

Check the style URL on OpenFreeMap's site before using it. Skip login for the demo: keep the user's sensitivity and travel mode in browser state, and add Supabase Auth only if time remains after the Day 2 gate.

**Store the secrets in SSM for the deployed Lambdas** (bash; run once per key):

```bash
for k in OPENAQ_API_KEY FIRMS_MAP_KEY ORS_API_KEY CONTACT_EMAIL SUPABASE_URL SUPABASE_SERVICE_KEY MODEL_BUCKET; do
  read -s -p "$k: " v; echo
  aws ssm put-parameter --name "/airguard/$k" --type SecureString \
    --value "$v" --overwrite --region us-east-1
done
```

**Attributions to show in the app footer and README:** OpenAQ, Open-Meteo with CAMS, NASA FIRMS, OpenStreetMap contributors, and OpenRouteService. Several of these licenses require it.

## Appendix B: Repo bootstrap and local environment

Run these in order on Day 1; each block is one step. The layout adds two folders to the earlier one: `common/` for shared config and database helpers, and `scripts/` for one-off jobs.

**1. Repo and Python environment**

```bash
mkdir airguard && cd airguard && git init
mkdir -p contracts common ingestion ml engine api agent infra scripts docs tests
touch common/__init__.py ingestion/__init__.py ml/__init__.py engine/__init__.py api/__init__.py agent/__init__.py
python3.12 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

**2. `requirements.txt`** (this file also goes into the Lambda image):

```text
fastapi
mangum
httpx
pydantic
numpy
xgboost-cpu
strands-agents
boto3
```

**`requirements-dev.txt`:**

```text
-r requirements.txt
pytest
pandas
scikit-learn
uvicorn[standard]
python-dotenv
ipykernel
strands-agents[ollama]
```

The `xgboost-cpu` package is a smaller build without GPU support and is published for x86\_64 Linux and Windows. On an Apple Silicon Mac, install `xgboost` locally for training and keep `xgboost-cpu` in the Lambda image. After the first successful install, run `pip freeze > requirements.lock` and pin versions.

**3. Install and configure**

```bash
pip install -r requirements-dev.txt
cp .env.example .env        # then fill in the keys from Appendix A
```

**4. `.gitignore` essentials**

```text
.env
.venv/
__pycache__/
node_modules/
.aws-sam/
frontend/.next/
models/
data/
```

**5. AWS tooling and a models bucket**

```bash
pip install aws-sam-cli                # or use AWS's installer
aws --version; sam --version; docker --version
aws configure                          # region us-east-1
aws s3 mb s3://airguard-models-<your-suffix> --region us-east-1
```

Docker must be running for `sam build`, because the Lambdas ship as one container image (Appendix F). On Apple Silicon, building an x86\_64 image runs under emulation and is slower.

**6. Local LLM for development**

```bash
ollama pull llama3.1      # pick a model that supports tool calling
ollama serve              # skip if the Ollama app is already running
```

**7. Frontend**

```bash
npx create-next-app@latest frontend --typescript --tailwind --eslint --app
cd frontend && npm install maplibre-gl recharts && cd ..
```

**8. Contracts from code.** Write the Pydantic request and response models first (Appendix F). FastAPI then produces the OpenAPI file, and the frontend can generate types from it:

```bash
uvicorn api.main:app --port 8000 &
curl -s localhost:8000/openapi.json > contracts/openapi.json
npx openapi-typescript contracts/openapi.json -o frontend/src/api-types.ts
```

**Daily commands**

| Task | Command |
| --- | --- |
| Run the API locally | `uvicorn api.main:app --reload --port 8000` |
| Run tests | `pytest -q` |
| Run the frontend | `cd frontend && npm run dev` |
| Build and deploy | `sam build -t infra/template.yaml && sam deploy --guided` (first time) |
| Tail Lambda logs | `sam logs -n ApiFunction --stack-name airguard --tail` |

## Appendix C: Data ingestion code

This appendix gives working starter code for the shared helpers, the three data sources, and a one-time backfill. Endpoints and limits below were checked against each provider's docs.

**Facts checked against the docs**

- **OpenAQ v3:** base `https://api.openaq.org/v3`, key in the `X-API-Key` header. `GET /locations` accepts `bbox` (minLon,minLat,maxLon,maxLat), `parameters_id` (PM2.5 is `2`), `limit` and `page`. `GET /sensors/{id}/hours` returns precomputed hourly values; `GET /locations/{id}/latest` returns the newest reading. Free limits are 60 requests/minute and 2,000/hour, and a 429 response means wait for the reset in the `x-ratelimit-reset` header.
- **Open-Meteo weather:** `https://api.open-meteo.com/v1/forecast` takes `past_days` (0 to 92) and several comma-separated coordinates in one call. History comes from `https://archive-api.open-meteo.com/v1/archive` with `start_date` and `end_date`; its ERA5 data arrives with about a 5-day delay, and `boundary_layer_height` is listed there as an additional variable.
- **Open-Meteo air quality:** `https://air-quality-api.open-meteo.com/v1/air-quality` with `hourly=pm2_5`. Over India it uses the global CAMS model at about 45 km and 3-hourly steps, so use it only as a coarse baseline, not as a station-level truth. This guide has no code for it, so treat it as an optional extension.
- **NASA FIRMS:** `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{west,south,east,north}/{DAY_RANGE}[/{DATE}]`. Sources include `VIIRS_SNPP_NRT` (recent) and `VIIRS_SNPP_SP` (standard processing, older dates). A date plus day range returns DATE through DATE + DAY\_RANGE − 1.

**SQL changes to the schema** (the engine does distance math in Python, so plain latitude and longitude columns are easier than the geography column):

```sql
alter table stations
  add column if not exists lat double precision,
  add column if not exists lon double precision,
  add column if not exists sensor_id bigint,
  add column if not exists last_seen timestamptz;
alter table stations alter column geom drop not null;
```

**`common/config.py`** (environment locally, SSM parameters on Lambda):

```python
import functools
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is not installed in the Lambda image
    pass


@functools.lru_cache(maxsize=1)
def cfg() -> dict:
    if os.environ.get("LOCAL") == "1":
        return dict(os.environ)
    import boto3
    out = dict(os.environ)
    resp = boto3.client("ssm").get_parameters_by_path(Path="/airguard/", WithDecryption=True)
    for p in resp["Parameters"]:  # up to 10 per page; this project uses 7
        out[p["Name"].rsplit("/", 1)[-1]] = p["Value"]
    return out
```

**`common/db.py`** (Supabase through its REST interface, so no heavy client library is needed):

```python
import httpx
from common.config import cfg


def _h(extra=None):
    key = cfg()["SUPABASE_SERVICE_KEY"]
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", **(extra or {})}


def _url(table):
    return cfg()["SUPABASE_URL"].rstrip("/") + f"/rest/v1/{table}"


def select(table, **params):
    """select('forecasts', select='*', station_id='eq.123', order='target_ts.asc', limit=100)"""
    r = httpx.get(_url(table), headers=_h(), params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def upsert(table, rows, on_conflict, chunk=500):
    keys = [k.strip() for k in on_conflict.split(",")]
    unique = {tuple(r.get(k) for k in keys): r for r in rows}   # one row per conflict key; the last one wins
    if len(unique) < len(rows):
        print(f"upsert {table}: dropped {len(rows) - len(unique)} duplicate rows")
    rows = list(unique.values())
    for i in range(0, len(rows), chunk):
        r = httpx.post(
            _url(table),
            headers=_h({"Prefer": "resolution=merge-duplicates,return=minimal"}),
            params={"on_conflict": on_conflict},
            json=rows[i:i + chunk],
            timeout=60,
        )
        r.raise_for_status()
```

**`common/geo.py`:**

```python
import math

R_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_KM * math.asin(math.sqrt(a))
```

**`ingestion/openaq.py`:**

```python
import time
from datetime import datetime, timedelta, timezone

import httpx

from common.config import cfg

BASE = "https://api.openaq.org/v3"
DELHI_BBOX = "76.80,28.35,77.55,28.95"  # minLon,minLat,maxLon,maxLat: Delhi NCR, approximate
PM25 = 2


def get(path, **params):
    for _ in range(5):
        time.sleep(1.1)  # stay under 60 requests/minute
        r = httpx.get(BASE + path, params=params, headers={"X-API-Key": cfg()["OPENAQ_API_KEY"]}, timeout=30)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("x-ratelimit-reset", 60)) + 1)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("OpenAQ keeps returning 429")


def pm25_stations(active_days=7):
    out, page = [], 1
    while True:
        j = get("/locations", bbox=DELHI_BBOX, parameters_id=PM25, limit=1000, page=page)
        for loc in j["results"]:
            sensor = next((s for s in loc.get("sensors", []) if s["parameter"]["id"] == PM25), None)
            if not sensor:
                continue
            last = (loc.get("datetimeLast") or {}).get("utc")
            active = bool(last) and datetime.fromisoformat(last.replace("Z", "+00:00")) > datetime.now(timezone.utc) - timedelta(days=active_days)
            out.append({"id": str(loc["id"]), "name": loc["name"], "lat": loc["coordinates"]["latitude"],
                        "lon": loc["coordinates"]["longitude"], "sensor_id": sensor["id"], "last_utc": last, "active": active})
        if len(j["results"]) < 1000:
            return out
        page += 1


def hourly_pm25(sensor_id, start_iso, end_iso):
    rows, page = [], 1
    while True:
        j = get(f"/sensors/{sensor_id}/hours", datetime_from=start_iso, datetime_to=end_iso, limit=1000, page=page)
        for r in j["results"]:
            v = r.get("value")
            if v is not None and 0 <= v <= 1000:  # drop negatives and sentinel values
                rows.append({"ts": r["period"]["datetimeFrom"]["utc"], "value": v})
        if len(j["results"]) < 1000:
            return rows
        page += 1
```

The response field names for `/hours` and `/locations` come from the docs' descriptions. On Day 1, print one raw result of each and adjust the key names if they differ.

**`ingestion/weather.py`:**

```python
import httpx

HOURLY_BASE = "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"
HOURLY = HOURLY_BASE + ",boundary_layer_height"


def _get(url, params, timeout):
    r = httpx.get(url, params=params, timeout=timeout)
    if r.status_code == 400 and "boundary_layer_height" in params["hourly"]:   # this endpoint doesn't offer the variable
        r = httpx.get(url, params={**params, "hourly": HOURLY_BASE}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _rows(j, stations):
    items = j if isinstance(j, list) else [j]  # several coordinates return a list
    rows = []
    for s, item in zip(stations, items):
        h = item["hourly"]
        for i, t in enumerate(h["time"]):
            rows.append({"station_id": s["id"], "ts": t + ":00+00:00", "temp": h["temperature_2m"][i],
                         "humidity": h["relative_humidity_2m"][i], "wind_speed": h["wind_speed_10m"][i],
                         "wind_dir": h["wind_direction_10m"][i], "blh": h.get("boundary_layer_height", [None] * len(h["time"]))[i]})
    return rows


def _common(stations):
    return {"latitude": ",".join(str(s["lat"]) for s in stations), "longitude": ",".join(str(s["lon"]) for s in stations),
            "hourly": HOURLY, "wind_speed_unit": "ms", "timezone": "UTC"}


def fetch_recent(stations, past_days=3, forecast_days=2):
    j = _get("https://api.open-meteo.com/v1/forecast",
             {**_common(stations), "past_days": past_days, "forecast_days": forecast_days}, 60)
    return _rows(j, stations)


def fetch_archive(stations, start, end):
    j = _get("https://archive-api.open-meteo.com/v1/archive",
             {**_common(stations), "start_date": str(start), "end_date": str(end)}, 120)
    return _rows(j, stations)
```

If the archive response lacks `boundary_layer_height` for a model, the request falls back to the other variables and `blh` is stored as missing. Train with DROP\_FEATURES=blh in that case rather than filling it with guesses.

**`ingestion/fires.py`** (counts fires upwind by 45-degree sector, so a feature lookup is a table read instead of a distance calculation per hour):

```python
import csv
import io
import math
from datetime import date, timedelta

import httpx
import numpy as np

from common.config import cfg

FIRMS = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
REGION = "73.5,28.0,78.0,32.5"  # west,south,east,north: Punjab, Haryana, Delhi NCR (approximate)


def fetch(day_range, start=None, source="VIIRS_SNPP_NRT"):
    url = f"{FIRMS}/{cfg()['FIRMS_MAP_KEY']}/{source}/{REGION}/{day_range}" + (f"/{start}" if start else "")
    r = httpx.get(url, timeout=90)
    r.raise_for_status()
    if not r.text.startswith("latitude"):
        if r.text.strip() == "":
            return []
        raise RuntimeError(r.text[:200])  # for example an invalid MAP_KEY message
    return [{"lat": float(x["latitude"]), "lon": float(x["longitude"]), "day": date.fromisoformat(x["acq_date"])}
            for x in csv.DictReader(io.StringIO(r.text))]


def fetch_range(start: date, end: date, window=5):
    out, d = [], start
    while d <= end:
        rows = fetch(window, d, "VIIRS_SNPP_SP") or fetch(window, d, "VIIRS_SNPP_NRT")
        out += rows
        d += timedelta(days=window)
    return out


def sector_table(stations, fires, start: date, end: date, min_km=20, max_km=400):
    """{station_id: array[n_days, 8]} = fires detected on the 2 complete days before each day, per 45-degree sector (index 0 = north), so nothing from the current day leaks in."""
    n = (end - start).days + 1
    f_lat = np.radians(np.array([f["lat"] for f in fires], dtype=float))
    f_lon = np.radians(np.array([f["lon"] for f in fires], dtype=float))
    f_day = np.array([(f["day"] - start).days for f in fires], dtype=int)
    out = {}
    for s in stations:
        lat1, lon1 = math.radians(s["lat"]), math.radians(s["lon"])
        dl = f_lon - lon1
        a = np.sin((f_lat - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(f_lat) * np.sin(dl / 2) ** 2
        dist = 2 * 6371.0088 * np.arcsin(np.sqrt(a))
        y = np.sin(dl) * np.cos(f_lat)
        x = np.cos(lat1) * np.sin(f_lat) - np.sin(lat1) * np.cos(f_lat) * np.cos(dl)
        brg = (np.degrees(np.arctan2(y, x)) + 360) % 360
        keep = (dist >= min_km) & (dist <= max_km) & (f_day >= 0) & (f_day < n)
        sector = (((brg[keep] + 22.5) // 45) % 8).astype(int)
        daily = np.zeros((n, 8))
        np.add.at(daily, (f_day[keep], sector), 1)
        prev2 = np.zeros_like(daily)
        prev2[1:] += daily[:-1]          # yesterday
        prev2[2:] += daily[:-2]          # the day before yesterday
        out[s["id"]] = prev2             # row d = detections from days d-1 and d-2, both complete before day d starts
    return out


def upwind_count(table, station_id, start: date, ts, wind_from_deg):
    arr = table.get(station_id)
    d = (ts.date() - start).days
    if arr is None or wind_from_deg is None or not (0 <= d < len(arr)):
        return 0
    return int(arr[d][int(((wind_from_deg + 22.5) // 45) % 8)])
```

Each day's counts use only the two complete days before it, so a forecast issued in the morning never sees detections from later that day. Wind direction in Open-Meteo is the direction the wind blows from, so a fire is upwind when its bearing from the station falls in the sector that contains the wind direction. The FIRMS page lists the maximum allowed day range, so check that 5 days is inside it, and use the `data_availability` endpoint to see each source's date coverage.

**`scripts/backfill.py`** (run once on Day 1; about 5 to 10 minutes within OpenAQ's rate limit for 30 stations and a year of hours):

```python
from datetime import datetime, timedelta, timezone

from common import db
from ingestion import fires, openaq, weather


def chunks(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def main(days=365):
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    stations = [s for s in openaq.pm25_stations() if s["active"]]
    print("active PM2.5 stations:", len(stations))
    db.upsert("stations", [{"id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"],
                            "sensor_id": s["sensor_id"], "last_seen": s["last_utc"]} for s in stations], "id")
    for s in stations:
        rows = openaq.hourly_pm25(s["sensor_id"], start.isoformat(), end.isoformat())
        db.upsert("measurements", [{"station_id": s["id"], "pollutant": "pm25", "unit": "µg/m³", **r} for r in rows],
                  "station_id,pollutant,ts")
        print(s["name"], len(rows), "hourly values")
    fire_list = fires.fetch_range(start.date(), end.date())
    table = fires.sector_table(stations, fire_list, start.date(), end.date())
    for batch in chunks(stations, 10):
        wx = weather.fetch_recent(batch, past_days=14, forecast_days=0)
        wx += weather.fetch_archive(batch, start.date(), (end - timedelta(days=8)).date())   # archive last: it wins on overlap
        for w in wx:
            w["fires_upwind"] = fires.upwind_count(table, w["station_id"], start.date(), datetime.fromisoformat(w["ts"]), w["wind_dir"])
        db.upsert("weather", wx, "station_id,ts")


if __name__ == "__main__":
    main()
```

**Sanity checks after the backfill**

1. The number of active PM2.5 stations printed at the start. Under 8 means narrowing the area (see Appendix K).
2. Hours of history per station: `select station_id, count(*), min(ts), max(ts) from measurements group by 1;`
3. Fraction of missing hours per station; drop stations that are mostly empty.
4. Spot-check one hour of PM2.5 against the station's page on OpenAQ's Explore site.

## Appendix D: Features, training, backtest, and hourly prediction

The same feature function builds rows for training and for the hourly Lambda, which prevents train/serve mismatch. All timestamps are UTC, converted to naive hours with `hour()`. One XGBoost model is trained per horizon; XGBoost handles missing lag values natively, so gaps in a station's history don't force rows to be dropped.

**Extra SQL:** a table that holds only the newest forecast per station and horizon (horizon 0 is the latest observation), plus row-level security, so the public key can't read your tables and only the backend's service key can.

```sql
alter table eval_metrics
  add column if not exists baseline_persistence_rmse double precision,
  add column if not exists baseline_hourly_mean_rmse double precision,
  add column if not exists interval_coverage double precision,
  add column if not exists interval_width double precision;

create table if not exists forecasts_latest (
  station_id text references stations(id),
  horizon_h integer not null,
  target_ts timestamptz not null,
  pm25_pred double precision,
  pm25_low double precision,
  pm25_high double precision,
  model_version text,
  generated_at timestamptz default now(),
  primary key (station_id, horizon_h)
);

do $$ declare t text; begin
  foreach t in array array['stations','measurements','weather','forecasts','forecasts_latest',
                           'eval_metrics','route_cache'] loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;
```

**`ml/features.py`**

```python
import math
import os
from datetime import datetime, timedelta

import numpy as np

from common.geo import haversine_km

HORIZONS = [int(h) for h in os.environ.get("HORIZONS", "1,3,6,12,24").split(",")]   # e.g. HORIZONS=1,3,6 when history is thin
FEATURES = [
    "now", "lag1", "lag3", "lag6", "lag24", "mean6", "mean24",
    "hod_sin", "hod_cos", "dow",
    "temp", "rh", "wind", "wind_u", "wind_v", "blh", "fires_upwind",
    "nbr_mean",
]
NAN = float("nan")


def hour(ts: str) -> datetime:
    """UTC ISO string -> naive datetime floored to the hour. All inputs must be UTC."""
    d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return d.replace(tzinfo=None, minute=0, second=0, microsecond=0)


def neighbors(stations, k=3):
    out = {}
    for s in stations:
        ranked = sorted((haversine_km(s["lat"], s["lon"], o["lat"], o["lon"]), o["id"]) for o in stations if o["id"] != s["id"])
        out[s["id"]] = [i for _, i in ranked[:k]]
    return out


def interval(p, q10, q90):
    """Forecast range with the guarantee 0 <= low <= p <= high."""
    return max(0.0, min(p, p + q10)), max(p, p + q90)


def _uv(speed, deg):
    if speed is None or deg is None:
        return NAN, NAN
    r = math.radians(deg)  # wind blows FROM deg
    return -speed * math.sin(r), -speed * math.cos(r)


def _f(x):
    return NAN if x is None else float(x)


def row(sid, t, h, pm, wx, nbrs):
    """Feature vector for station sid, issue time t, horizon h hours; None if the essentials are missing."""
    s = pm[sid]
    now = s.get(t)
    w = wx[sid].get(t)
    if now is None or w is None:
        return None
    lag = lambda k: s.get(t - timedelta(hours=k), NAN)
    last6 = [v for k in range(6) if (v := s.get(t - timedelta(hours=k))) is not None]
    last24 = [v for k in range(24) if (v := s.get(t - timedelta(hours=k))) is not None]
    nb = [v for n in nbrs.get(sid, []) if (v := pm[n].get(t)) is not None]
    u, v_ = _uv(w["wind_speed"], w["wind_dir"])
    return [
        now, lag(1), lag(3), lag(6), lag(24),
        sum(last6) / len(last6) if len(last6) >= 4 else NAN,
        sum(last24) / len(last24) if len(last24) >= 16 else NAN,
        math.sin(2 * math.pi * t.hour / 24), math.cos(2 * math.pi * t.hour / 24), float(t.weekday()),
        _f(w["temp"]), _f(w["humidity"]), _f(w["wind_speed"]), u, v_, _f(w["blh"]), _f(w.get("fires_upwind")),
        sum(nb) / len(nb) if nb else NAN,
    ]


def build_dataset(stations, pm, wx, issue_times, h):
    nbrs = neighbors(stations)
    X, y, meta = [], [], []
    for st in stations:
        sid = st["id"]
        for t in issue_times:
            target = pm[sid].get(t + timedelta(hours=h))
            if target is None:
                continue
            x = row(sid, t, h, pm, wx, nbrs)
            if x is not None:
                X.append(x); y.append(target); meta.append((sid, t))
    return np.array(X, dtype=float).reshape(-1, len(FEATURES)), np.array(y, dtype=float), meta   # an empty result keeps 2 dimensions
```

Weather features describe conditions at the issue time only. An earlier draft also fed in weather at the target hour; it was removed because training would use observed weather while serving could only use a forecast, which makes the backtest look better than production. If you want forecast weather later, train on archived forecasts (Open-Meteo's Historical Forecast or Previous Model Runs APIs), not on reanalysis. Training also uses archived weather while serving uses the forecast API's values for the past hours, so the backtest does not fully validate the live weather path. Compare the two for the same hours (mean difference and correlation), say what you found, and run the live check below.

**`ml/train.py`** (run with `python -m ml.train`; building 5 horizons for about 30 stations takes a few minutes in plain Python):

```python
import json
import os
from datetime import timedelta

import numpy as np
import xgboost as xgb

from common import db
from ml.features import FEATURES, HORIZONS, build_dataset, hour, neighbors

VERSION = os.environ.get("MODEL_VERSION", "v1")
DROP = set(filter(None, os.environ.get("DROP_FEATURES", "").split(",")))   # for ablations, e.g. DROP_FEATURES=fires_upwind


def paged(table, page=1000, **params):
    out, off = [], 0
    while True:
        rows = db.select(table, limit=page, offset=off, order="ts.asc", **params)
        out += rows
        if len(rows) < page:
            return out
        off += page


def load():
    stations = db.select("stations", select="id,name,lat,lon,sensor_id")
    pm, wx = {}, {}
    for s in stations:
        sid = s["id"]
        rows = paged("measurements", station_id=f"eq.{sid}", pollutant="eq.pm25", select="ts,value")
        pm[sid] = {hour(r["ts"]): r["value"] for r in rows}
        w = paged("weather", station_id=f"eq.{sid}", select="ts,temp,humidity,wind_speed,wind_dir,blh,fires_upwind")
        wx[sid] = {hour(r["ts"]): r for r in w}
    return stations, pm, wx


def mae(a, b):
    return float(np.mean(np.abs(a - b)))


def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def main():
    stations, pm, wx = load()
    stations = [s for s in stations if len(pm[s["id"]]) > 24 * 60]  # at least 60 days of hourly values
    print(f"{len(stations)} stations have more than 60 days of hourly PM2.5")
    if len(stations) < 3:
        raise SystemExit("Too few stations with enough history. Check the backfill, narrow the area, or lower the 60-day rule (Appendix K).")
    hours = sorted({t for s in stations for t in pm[s["id"]]})
    end = hours[-1]
    test_start = end - timedelta(days=14)
    val_start = test_start - timedelta(days=14)
    os.makedirs(f"models/{VERSION}", exist_ok=True)
    residual_q, rows_out = {}, []
    for h in HORIZONS:
        X, y, meta = build_dataset(stations, pm, wx, hours, h)
        if len(y) == 0:
            print(f"+{h}h: no usable rows (missing history or weather). Skipping it.")
            continue
        X = X[:, [i for i, f in enumerate(FEATURES) if f not in DROP]]   # column 0 ("now") always stays
        tgt = [t + timedelta(hours=h) for _, t in meta]
        tr = np.array([a < val_start for a in tgt])                       # target before the validation window
        va = np.array([t >= val_start and a < test_start for (_, t), a in zip(meta, tgt)])
        te = np.array([t >= test_start for _, t in meta])                 # untouched final window
        n_tr, n_va, n_te = int(tr.sum()), int(va.sum()), int(te.sum())
        print(f"+{h}h: {n_tr} train, {n_va} validation, {n_te} test rows")
        if min(n_tr, n_va, n_te) < 200:
            print(f"  skipping +{h}h: need at least 200 rows in each split. Remove it from HORIZONS.")
            continue
        model = xgb.XGBRegressor(n_estimators=600, learning_rate=0.05, max_depth=6, subsample=0.8,
                                 colsample_bytree=0.8, min_child_weight=5, early_stopping_rounds=30,
                                 tree_method="hist", n_jobs=-1)
        model.fit(X[tr], y[tr], eval_set=[(X[va], y[va])], verbose=False)
        res = y[va] - np.maximum(0.0, model.predict(X[va]))
        residual_q[str(h)] = [float(np.quantile(res, 0.1)), float(np.quantile(res, 0.9))]
        print({"horizon_h": h, "val_mae": round(float(np.mean(np.abs(res))), 2)})   # compare ablations on this, not on test
        hod = {}
        for i in np.where(tr)[0]:
            sid, t = meta[i]
            hod.setdefault((sid, (t + timedelta(hours=h)).hour), []).append(y[i])
        hod = {k: float(np.mean(v)) for k, v in hod.items()}
        gm = float(np.mean(y[tr]))
        idx = np.where(te)[0]
        p_hod = np.array([hod.get((meta[i][0], (meta[i][1] + timedelta(hours=h)).hour), gm) for i in idx])
        p_model, p_pers, yt = np.maximum(0.0, model.predict(X[te])), X[te][:, 0], y[te]
        q10, q90 = residual_q[str(h)]
        lo = np.maximum(0.0, np.minimum(p_model, p_model + q10))   # same guarantee as ml.features.interval
        hi = np.maximum(p_model, p_model + q90)
        cov, wid = float(np.mean((yt >= lo) & (yt <= hi))), float(np.mean(hi - lo))   # the 10-90 range should cover about 80%
        rows_out.append({"model_version": VERSION, "horizon_h": h, "mae": round(mae(yt, p_model), 2),
                         "rmse": round(rmse(yt, p_model), 2),
                         "baseline_persistence_mae": round(mae(yt, p_pers), 2),
                         "baseline_hourly_mean_mae": round(mae(yt, p_hod), 2),
                         "baseline_persistence_rmse": round(rmse(yt, p_pers), 2),
                         "baseline_hourly_mean_rmse": round(rmse(yt, p_hod), 2),
                         "interval_coverage": round(cov, 3), "interval_width": round(wid, 2), "n_samples": int(te.sum())})
        print(rows_out[-1])
        model.save_model(f"models/{VERSION}/h{h}.json")
    if not residual_q:
        raise SystemExit("No horizon had enough data. Fix the data first (Appendix K).")
    meta_out = {"version": VERSION, "features": [f for f in FEATURES if f not in DROP], "horizons": sorted(int(h) for h in residual_q), "residual_q": residual_q,
                "stations": stations, "neighbors": neighbors(stations), "trained_through": str(end),
                "test_start": str(test_start)}
    json.dump(meta_out, open(f"models/{VERSION}/meta.json", "w"))
    db.upsert("eval_metrics", rows_out, "model_version,horizon_h")


if __name__ == "__main__":
    main()
```

Then upload the model files:

```bash
export MODEL_VERSION=v1        # or v1nofire, whichever you chose after the ablation
aws s3 sync models/$MODEL_VERSION s3://$MODEL_BUCKET/models/$MODEL_VERSION
```

**How the split works.** Training rows have targets before the validation window, validation (used for early stopping and the 10th and 90th percentile residuals that become the forecast range) is the next 14 days, and the last 14 days are a final test window that nothing was tuned on. The test window's numbers go into `eval_metrics`. Delhi's pollution is strongly seasonal, so note in the pitch that the test window covers only one season, and if you have a year of data, consider also testing on a window from last winter.

**How to read the results**

- The model should beat persistence and the hour-of-day average at the longer horizons (6, 12, 24 hours). At +1 hour persistence is hard to beat, so don't be surprised if the model only ties.
- Report the numbers as they are, including horizons where the model does not win. Lead with the horizons where it does.
- Don't re-tune after looking at the test window. If you change features, rerun with a fresh holdout or say so.

**Ablation: keep the fire feature only if it earns its place.** Train twice and compare on the validation window, not the test window, so you are not choosing features by peeking at the final test:

```bash
MODEL_VERSION=v1 python -m ml.train                                   # with fires_upwind
MODEL_VERSION=v1nofire DROP_FEATURES=fires_upwind python -m ml.train   # without it
```

Each run prints a `val_mae` line per horizon. Decision rule (my judgement; adjust it, but fix it before you look): keep `fires_upwind` only if validation MAE improves at three or more of the five horizons by more than about 2%. If it doesn't, ship the `v1nofire` models (set `MODEL_VERSION=v1nofire` and upload that folder, then deploy with ModelVersion=v1nofire and point MODEL\_DIR at it locally, so every place loads the same one), and use the fire data only as an optional map layer or drop it. Then report the test-window numbers once, for the version you chose. Whatever you decide, say so in the method notes. Rerun the ablation after any change to how the fire feature is built.

**`ingestion/handler.py`** (the hourly Lambda: fetch recent data, predict, store):

```python
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

import boto3
import numpy as np
import xgboost as xgb

from common import db
from common.config import cfg
from ingestion import fires, openaq, weather
from ml.features import FEATURES, hour, interval, row

_M = {}


def load_models():
    if _M:
        return _M
    version = os.environ.get("MODEL_VERSION", "v1")
    s3, d = boto3.client("s3"), tempfile.mkdtemp()
    s3.download_file(cfg()["MODEL_BUCKET"], f"models/{version}/meta.json", f"{d}/meta.json")
    meta = json.load(open(f"{d}/meta.json"))
    models = {}
    for h in meta["horizons"]:
        s3.download_file(cfg()["MODEL_BUCKET"], f"models/{version}/h{h}.json", f"{d}/h{h}.json")
        m = xgb.XGBRegressor()
        m.load_model(f"{d}/h{h}.json")
        models[h] = m
    _M.update(meta=meta, models=models, version=version)
    return _M


def lambda_handler(event, context):
    M = load_models()
    meta, models = M["meta"], M["models"]
    stations, nbrs = meta["stations"], meta["neighbors"]
    now = datetime.now(timezone.utc)
    now_h = now.replace(tzinfo=None, minute=0, second=0, microsecond=0)

    pm = {}
    for s in stations:
        rows = openaq.hourly_pm25(s["sensor_id"], (now - timedelta(hours=36)).isoformat(), now.isoformat())
        pm[s["id"]] = {hour(r["ts"]): r["value"] for r in rows}
        db.upsert("measurements", [{"station_id": s["id"], "pollutant": "pm25", "unit": "µg/m³", **r} for r in rows],
                  "station_id,pollutant,ts")   # keep the history growing

    wrows = weather.fetch_recent(stations, past_days=2, forecast_days=1)
    start_d, end_d = (now_h - timedelta(days=4)).date(), now_h.date()
    table = fires.sector_table(stations, fires.fetch(5), start_d, end_d)
    wx = {s["id"]: {} for s in stations}
    for w in wrows:
        t = hour(w["ts"])
        w["fires_upwind"] = fires.upwind_count(table, w["station_id"], start_d, t, w["wind_dir"])
        wx[w["station_id"]][t] = w
    db.upsert("weather", [w for w in wrows if hour(w["ts"]) <= now_h], "station_id,ts")

    out, gen = [], now.isoformat()
    for s in stations:
        sid = s["id"]
        if not pm[sid]:
            continue
        t0 = max(pm[sid])
        if now_h - t0 > timedelta(hours=6):  # stale station: skip it
            continue
        base = {"station_id": sid, "model_version": M["version"], "generated_at": gen}
        out.append({**base, "horizon_h": 0, "target_ts": t0.isoformat() + "+00:00",
                    "pm25_pred": pm[sid][t0], "pm25_low": pm[sid][t0], "pm25_high": pm[sid][t0]})
        for h in meta["horizons"]:
            x = row(sid, t0, h, pm, wx, nbrs)
            if x is not None:
                x = [x[FEATURES.index(f)] for f in meta["features"]]   # same columns the model was trained on
            if x is None:
                continue
            p = max(0.0, float(models[h].predict(np.array([x]))[0]))
            q10, q90 = meta["residual_q"][str(h)]
            out.append({**base, "horizon_h": h, "target_ts": (t0 + timedelta(hours=h)).isoformat() + "+00:00",
                        "pm25_pred": p, "pm25_low": interval(p, q10, q90)[0], "pm25_high": interval(p, q10, q90)[1]})
    db.upsert("forecasts_latest", out, "station_id,horizon_h")
    db.upsert("forecasts", out, "station_id,horizon_h,target_ts,model_version")
    return {"stations": len({o["station_id"] for o in out}), "rows": len(out)}
```

Test it locally first with `python -c "from ingestion.handler import lambda_handler; print(lambda_handler({}, None))"` (with `LOCAL=1` and the model files in S3). It makes about one OpenAQ call per station, with a 1.1-second pause each, so the Lambda needs a timeout of a few minutes (set in Appendix F).

**Freshness rules.** The API only uses a station if its latest real reading (the horizon 0 row) is under 6 hours old, and only forecast rows from that same hourly run. Stale rows left over from earlier runs are ignored, not trusted. The data age shown in the app is the median age of the latest real readings, and `/health` reports the forecast generation time separately (`observation_age_min` and `forecast_age_min`). The hourly job also saves each new reading to `measurements`, so the history keeps growing after the one-time backfill. `common/db.py` now drops duplicate conflict keys inside one upsert (and prints how many), which also protects the weather backfill, where the archive and recent ranges overlap; the archive is written last so it wins.

**Interval guarantees and coverage.** `ml.features.interval()` guarantees `0 <= low <= prediction <= high` in both the hourly job and the evaluation. The evaluation also reports interval coverage and average width on the test window. The 10th to 90th percentile range should cover about 80% of observations; if coverage is far from that (say below 70%), say so on the evaluation page or widen the range before calling it calibrated. Add this test:

```python
# tests/test_interval.py
from ml.features import interval


def test_interval_invariant_near_zero():
    for p in (0.0, 0.5, 3.0, 80.0):
        for q10, q90 in ((-20, 10), (-5, -2), (2, 9), (-1, 1)):
            lo, hi = interval(p, q10, q90)
            assert 0 <= lo <= p <= hi
```

**Thin history.** If Appendix K check 2 shows less than about 90 days of data, train fewer horizons by setting the environment variable for one run:

```bash
HORIZONS=1,3,6 python -m ml.train
```

The script prints how many rows each split has and skips horizons with too little data, so `/eval` has one row per horizon that was trained.

**Live pipeline check.** The backtest uses archived weather, while the deployed job uses the forecast API's values, so the backtest does not fully validate the live path. After the hourly job has run for at least two days (a week is better), score the forecasts it actually made against the readings that arrived afterwards, and report this separately from the backtest as a "live pipeline check over N days":

```python
# scripts/live_check.py
from collections import defaultdict
from statistics import mean

from common import db
from ml.features import hour


def pages(table, **params):
    off = 0
    while True:
        rows = db.select(table, limit=1000, offset=off, **params)
        yield from rows
        if len(rows) < 1000:
            return
        off += 1000


def main():
    actual = {(r["station_id"], hour(r["ts"])): r["value"]
              for r in pages("measurements", select="station_id,ts,value", pollutant="eq.pm25", order="ts.asc")}
    errors = defaultdict(list)
    for r in pages("forecasts", select="station_id,horizon_h,target_ts,pm25_pred", horizon_h="gt.0", order="target_ts.asc"):
        a = actual.get((r["station_id"], hour(r["target_ts"])))
        if a is not None:
            errors[r["horizon_h"]].append(abs(a - r["pm25_pred"]))
    for h in sorted(errors):
        print(f"+{h}h: live MAE {mean(errors[h]):.1f} over {len(errors[h])} forecasts")


if __name__ == "__main__":
    main()
```

Run it with `PYTHONPATH=. python scripts/live_check.py` and compare the numbers with the backtest MAE. A large gap means the weather path or data freshness differs from training, and you should say so.

## Appendix E: Exposure engine algorithms, constants, and tests

The engine is pure Python with no network calls, which makes it fast to test. Its output is an exposure index, not a measured dose: it ranks routes against each other under stated assumptions.

**Constants and where they come from**

| Constant | Value | Status |
| --- | --- | --- |
| Segment length | 200 m | Design choice |
| Interpolation | Inverse-distance weighting, power 2, 4 nearest stations | Design choice; simple and explainable |
| Mode factor (relative intake per minute) | walk 1.0, cycle 1.6, car 0.5 | **Illustrative placeholders.** Replace with values from a source you cite, and show them in the app. |
| AirGuard exposure levels for mean PM2.5 (µg/m³) | 30 / 60 / 90 / 120 / 250 | Illustrative AirGuard levels, not official AQI categories. CPCB's PM2.5 categories are defined on 24-hour averages, so they are not applied to hourly values. Choose and justify your own cutoffs, or show only the µg/m³ value and the relative comparison. |
| Confidence | 0.6 × distance term + 0.4 × interval-width term | Heuristic reliability score, **not a probability**. Label it "data reliability". |
| Speed | Taken from the routing service's duration for the mode | Uniform speed along the route is assumed |
| Forecast horizon | Up to 24 hours ahead | Beyond that the series is held flat, so cap departures |

Metro is not supported in v1 because the routing service has no transit profile; the mode selector offers only walk, cycle, and car.

**`engine/exposure.py`**

```python
import math
from dataclasses import dataclass

from common.geo import haversine_km

MODES = {
    "walk": {"factor": 1.0, "ors_profile": "foot-walking"},
    "cycle": {"factor": 1.6, "ors_profile": "cycling-regular"},
    "car": {"factor": 0.5, "ors_profile": "driving-car"},
}
RISK_BANDS = [(30, "low"), (60, "moderate"), (90, "elevated"), (120, "high"), (250, "very_high"), (float("inf"), "extreme")]  # AirGuard levels, not official AQI categories
LEVEL_COLORS = {"low": "#2e7d32", "moderate": "#9e9d24", "elevated": "#f9a825", "high": "#e65100", "very_high": "#b71c1c", "extreme": "#4a148c"}


@dataclass
class Station:
    id: str
    lat: float
    lon: float
    series: list  # [(hours_from_now, pm25, low, high), ...] sorted by hours_from_now


def at_hour(series, h):
    """Linear interpolation in time; held flat outside the series."""
    if h <= series[0][0]:
        return tuple(series[0][1:])
    for (h0, *v0), (h1, *v1) in zip(series, series[1:]):
        if h <= h1:
            w = (h - h0) / (h1 - h0)
            return tuple(a + w * (b - a) for a, b in zip(v0, v1))
    return tuple(series[-1][1:])


def idw(lat, lon, stations, h, k=4, power=2.0):
    if not stations:
        raise ValueError("No usable air-quality stations right now.")
    ranked = sorted(((haversine_km(lat, lon, s.lat, s.lon), s) for s in stations), key=lambda x: x[0])[:k]
    nearest_km = ranked[0][0]
    if nearest_km < 0.05:
        pm, lo, hi = at_hour(ranked[0][1].series, h)
        return pm, lo, hi, nearest_km
    wts = [1 / d ** power for d, _ in ranked]
    vals = [at_hour(s.series, h) for _, s in ranked]
    tot = sum(wts)
    pm, lo, hi = (sum(w * v[i] for w, v in zip(wts, vals)) / tot for i in range(3))
    return pm, lo, hi, nearest_km


def resample(coords, step_m=200):
    """coords: [(lon, lat), ...] -> ([(lat, lon, length_m), ...] segment midpoints, total_m)."""
    pts = [(lat, lon) for lon, lat in coords]
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + haversine_km(a[0], a[1], b[0], b[1]) * 1000)
    total = cum[-1]
    if total == 0 or len(pts) < 2:
        return [(pts[0][0], pts[0][1], 0.0)], 0.0
    n = max(1, round(total / step_m))
    out, j = [], 0
    for i in range(n):
        target = (i + 0.5) * total / n
        while j < len(cum) - 2 and cum[j + 1] < target:
            j += 1
        seg = cum[j + 1] - cum[j]
        f = 0.0 if seg == 0 else (target - cum[j]) / seg
        out.append((pts[j][0] + f * (pts[j + 1][0] - pts[j][0]), pts[j][1] + f * (pts[j + 1][1] - pts[j][1]), total / n))
    return out, total


def segment_lines(coords, n):
    """Split the route into n equal-length pieces and return each piece's own points as [[lon, lat], ...],
    so the map can colour the real road, not a straight line between midpoints."""
    pts = [(lat, lon) for lon, lat in coords]
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + haversine_km(a[0], a[1], b[0], b[1]) * 1000)
    total = cum[-1]
    if total == 0 or len(pts) < 2:
        return [[[coords[0][0], coords[0][1]]] for _ in range(n)]

    def at(d):
        j = 0
        while j < len(cum) - 2 and cum[j + 1] < d:
            j += 1
        seg = cum[j + 1] - cum[j]
        f = 0.0 if seg == 0 else (d - cum[j]) / seg
        return [pts[j][1] + f * (pts[j + 1][1] - pts[j][1]), pts[j][0] + f * (pts[j + 1][0] - pts[j][0])]

    lines = []
    for i in range(n):
        d0, d1 = i * total / n, (i + 1) * total / n
        inner = [[pts[k][1], pts[k][0]] for k in range(len(pts)) if d0 < cum[k] < d1]
        lines.append([at(d0)] + inner + [at(d1)])
    return lines


def confidence(pm, lo, hi, nearest_km):
    c_dist = math.exp(-nearest_km / 8.0)                 # 1.0 at a station, 0.37 at 8 km
    c_width = 1.0 / (1.0 + (hi - lo) / max(pm, 10.0))    # narrower forecast range -> higher
    return 0.6 * c_dist + 0.4 * c_width


def level_config():
    """Single source of truth for levels, cutoffs and map colours; the API serves it at /config."""
    return [{"name": n, "max": None if c == float("inf") else c, "color": LEVEL_COLORS[n]} for c, n in RISK_BANDS]


def risk_label(mean_pm):
    return next(name for cutoff, name in RISK_BANDS if mean_pm <= cutoff)


def score_route(coords, duration_s, mode, depart_in_h, stations, step_m=200):
    segs, total_m = resample(coords, step_m)
    lines = segment_lines(coords, len(segs))
    seg_s = duration_s / len(segs)
    factor = MODES[mode]["factor"]
    exposure_index = pm_minutes = conf_sum = 0.0
    out = []
    for i, (lat, lon, _) in enumerate(segs):
        t_h = depart_in_h + (i + 0.5) * seg_s / 3600      # hours from now when we reach this segment
        pm, lo, hi, d_km = idw(lat, lon, stations, t_h)
        minutes = seg_s / 60
        exposure_index += pm * minutes * factor
        pm_minutes += pm * minutes
        conf_sum += confidence(pm, lo, hi, d_km)
        out.append({"lat": round(lat, 5), "lon": round(lon, 5), "pm25": round(pm, 1), "minutes": round(minutes, 2),
                    "line": [[round(x, 5), round(y, 5)] for x, y in lines[i]]})
    mean_pm = pm_minutes / (duration_s / 60)
    return {"duration_min": round(duration_s / 60, 1), "distance_km": round(total_m / 1000, 2), "exposure_index": round(exposure_index, 1),
            "mean_pm25": round(mean_pm, 1), "risk": risk_label(mean_pm), "confidence": round(conf_sum / len(segs), 2),
            "segments": out}


PREFERENCES = {  # extra minutes the user will accept per 10% reduction in exposure (illustrative; justify your own)
    "normal": 4.0,
    "sensitive": 7.0,
    "high": 10.0,
}


def choose(options, sensitivity="normal", max_extra_min=15, max_wait_min=120):
    """Pick the lowest-exposure option whose extra time is justified by its exposure reduction.
    Sensitivity changes only this decision rule, never the exposure estimate itself."""
    base = min((o for o in options if o["wait_min"] == 0), key=lambda o: o["duration_min"])   # fastest route, leave now
    k = PREFERENCES.get(sensitivity, PREFERENCES["normal"])
    acceptable = []
    for o in options:
        extra = o["wait_min"] + o["duration_min"] - base["duration_min"]
        gain = 100 * (base["exposure_index"] - o["exposure_index"]) / base["exposure_index"] if base["exposure_index"] else 0.0
        if o["wait_min"] <= max_wait_min and extra <= max_extra_min and extra <= k * gain / 10:
            acceptable.append({**o, "extra_min": round(extra, 1), "exposure_change_pct": round(-gain, 1)})
    chosen = min(acceptable, key=lambda o: (o["exposure_index"], o["extra_min"]))   # the baseline always qualifies
    return {"options": options, "baseline": base, "recommended": chosen,
            "delta": {"exposure_index_pct": chosen["exposure_change_pct"], "arrival_min": chosen["extra_min"]},
            "preference": {"sensitivity": sensitivity, "minutes_per_10pct": k, "max_extra_min": max_extra_min, "max_wait_min": max_wait_min}}


def best_departure(routes, mode, stations, earliest_in_h=0.0, window_h=4.0, max_wait_min=120, step_min=15,
                   sensitivity="normal", max_extra_min=15):
    """routes: [{'id', 'coords', 'duration_s'}]. Builds every route-and-time option, then lets choose() pick the recommendation."""
    options, t = [], earliest_in_h
    while t <= earliest_in_h + window_h + 1e-9:
        for r in routes:
            s = score_route(r["coords"], r["duration_s"], mode, t, stations)
            options.append({"depart_in_h": round(t, 3), "wait_min": round((t - earliest_in_h) * 60), "route_id": r["id"],
                            **{k: s[k] for k in ("duration_min", "exposure_index", "mean_pm25", "risk", "confidence")}})
        t += step_min / 60
    return choose(options, sensitivity, max_extra_min, max_wait_min)
```

**`tests/test_engine.py`**

```python
import pytest

from engine.exposure import Station, best_departure, choose, score_route

ROUTE_A = [(77.20, 28.60), (77.21, 28.60)]   # (lon, lat), about 1 km east-west
ROUTE_B = [(77.30, 28.70), (77.31, 28.70)]


def flat(pm, lat=28.60, lon=77.205, sid="s"):
    return Station(sid, lat, lon, [(0, pm, pm * 0.8, pm * 1.2), (24, pm, pm * 0.8, pm * 1.2)])


def test_uniform_field_exposure_index_equals_concentration_times_minutes_times_factor():
    r = score_route(ROUTE_A, 600, "walk", 0, [flat(50)])
    assert r["exposure_index"] == pytest.approx(50 * 10 * 1.0, rel=1e-6)
    assert r["mean_pm25"] == pytest.approx(50)


def test_mode_factor_scales_exposure_index():
    walk = score_route(ROUTE_A, 600, "walk", 0, [flat(50)])["exposure_index"]
    cycle = score_route(ROUTE_A, 600, "cycle", 0, [flat(50)])["exposure_index"]
    assert cycle == pytest.approx(walk * 1.6)


def test_route_near_hot_station_has_higher_exposure_index():
    stations = [flat(150, 28.60, 77.205, "hot"), flat(40, 28.70, 77.305, "cool")]
    a = score_route(ROUTE_A, 600, "walk", 0, stations)
    b = score_route(ROUTE_B, 600, "walk", 0, stations)
    assert a["exposure_index"] > b["exposure_index"]


def test_departure_moves_to_cleaner_hour():
    st = Station("s", 28.60, 77.205, [(0, 200, 160, 240), (1, 40, 30, 50), (24, 40, 30, 50)])
    res = best_departure([{"id": "r1", "coords": ROUTE_A, "duration_s": 600}], "walk", [st], window_h=4, max_wait_min=240,
                         sensitivity="high", max_extra_min=120)
    assert res["recommended"]["wait_min"] > 0
    assert res["delta"]["exposure_index_pct"] < 0


def test_segment_count_matches_length():
    r = score_route(ROUTE_A, 600, "walk", 0, [flat(50)])
    assert len(r["segments"]) == 5   # about 976 m at 200 m per segment


def opt(wait, dur, expo):
    return {"wait_min": wait, "duration_min": dur, "exposure_index": expo, "route_id": "r1"}


def test_sensitive_users_accept_more_extra_time_for_the_same_gain():
    options = [opt(0, 20, 100), opt(10, 20, 80)]   # +10 min for 20% lower exposure
    assert choose(options, "normal")["recommended"]["wait_min"] == 0
    assert choose(options, "sensitive")["recommended"]["wait_min"] == 10


def test_limits_are_hard_constraints():
    options = [opt(0, 20, 100), opt(60, 20, 10)]
    assert choose(options, "high", max_extra_min=15)["recommended"]["wait_min"] == 0
    assert choose(options, "high", max_extra_min=90, max_wait_min=30)["recommended"]["wait_min"] == 0


def test_segment_lines_follow_a_bend_in_the_route():
    bent = [(77.20, 28.60), (77.21, 28.60), (77.21, 28.61)]   # east, then north
    r = score_route(bent, 900, "walk", 0, [flat(50)])
    assert all(len(s["line"]) >= 2 for s in r["segments"])
    assert any(len(s["line"]) >= 3 for s in r["segments"])    # the piece containing the corner keeps it


def test_no_stations_gives_a_clear_error():
    with pytest.raises(ValueError):
        score_route(ROUTE_A, 600, "walk", 0, [])


def test_single_station_still_scores():
    assert score_route(ROUTE_A, 600, "walk", 0, [flat(50)])["exposure_index"] > 0
```

**Hand check (do this once):** pick one real route and two stations, compute the inverse-distance average and the exposure index for three segments in a spreadsheet, and confirm the engine returns the same numbers. Keep the sheet; it is evidence for the judges that the math was verified.

**What to say about limits.** The engine assumes uniform speed, ignores street-level variation (a road next to a busy junction versus a park), and relies on a handful of stations. The forecast range and the reliability score are how the app shows that honestly.

**Wording for the 15-minute steps.** The model forecasts at five horizons (+1, +3, +6, +12, and +24 hours). The engine interpolates linearly between those points so it can evaluate a departure every 15 minutes; those are scenario evaluations, not 15-minute forecasts. Say so on the about page and in the pitch, for example: "we forecast at five horizons up to 24 hours and interpolate between them to compare departure times every 15 minutes."

**Decision layer and shared thresholds.** `choose()` compares every route-and-time option with the fastest route leaving now. An option is acceptable if it respects the wait limit and the extra-minutes limit, and if its extra minutes are at most `PREFERENCES[sensitivity]` times its exposure reduction in percent, divided by 10. The recommendation is the acceptable option with the lowest exposure. `score_route` has no sensitivity parameter on purpose. The levels, cutoffs, and map colours live in one place (`RISK_BANDS` and `LEVEL_COLORS`), and the API serves them at `/config`, so the map, its legend, the about page, and the README should read them from there instead of repeating the numbers.

## Appendix F: Backend, container image, and SAM template

Three Lambdas share one container image: the API (FastAPI behind Mangum), the agent, and the hourly ingestion job. A container image avoids the 250 MB limit on zipped Lambdas, which the ML and agent libraries could exceed. The agent and API use forecasts that the ingestion job already stored, so neither needs to run the ML model.

**`api/service.py`** (shared by the API and the agent's tools):

```python
import hashlib
import json
import statistics
import time
from datetime import datetime, timezone

import httpx

from common import db
from common.config import cfg
from engine.exposure import MODES, Station, best_departure, idw, score_route

ORS = "https://api.openrouteservice.org/v2/directions"
MAX_OBS_AGE_MIN = 360   # a station whose latest real reading is older than this is left out (same rule as the hourly job)
PLACES = {  # approximate demo landmarks; verify on a map before relying on them (Appendix I)
    "connaught place": (28.6315, 77.2167), "india gate": (28.6129, 77.2295),
    "hauz khas": (28.5494, 77.2001), "du north campus": (28.6889, 77.2100),
}
_CACHE = {}
_LAST_GEO = [0.0]


def _cached(key, fn, ttl=300):
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = fn()
    _CACHE[key] = (time.time(), val)
    return val


def _ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_stations(demo=False):
    """Returns ([Station], median age in minutes of the latest real readings; not the forecast time). demo=True reads the frozen snapshot saved by scripts/snapshot.py."""
    if demo:
        snap = db.select("route_cache", select="response", key="eq.snapshot:stations")[0]["response"]
        return [Station(s["id"], s["lat"], s["lon"], [tuple(p) for p in s["series"]]) for s in snap["stations"]], None

    def fetch():
        names = {s["id"]: s for s in db.select("stations", select="id,lat,lon")}
        rows = db.select("forecasts_latest", select="station_id,horizon_h,target_ts,pm25_pred,pm25_low,pm25_high,generated_at")
        now = datetime.now(timezone.utc)
        by_station = {}
        for r in rows:
            by_station.setdefault(r["station_id"], []).append(r)
        sts, obs_ages = [], []
        for sid, rs in by_station.items():
            obs = next((r for r in rs if r["horizon_h"] == 0), None)      # horizon 0 = the latest real reading
            if obs is None or sid not in names:
                continue
            obs_age = (now - _ts(obs["target_ts"])).total_seconds() / 60
            if obs_age > MAX_OBS_AGE_MIN:                                 # stale station: leave it out
                continue
            run = [r for r in rs if r["generated_at"] == obs["generated_at"]]   # only rows from the same hourly run
            series = sorted(((_ts(r["target_ts"]) - now).total_seconds() / 3600, r["pm25_pred"], r["pm25_low"], r["pm25_high"]) for r in run)
            if len(series) >= 2:
                sts.append(Station(sid, names[sid]["lat"], names[sid]["lon"], series))
                obs_ages.append(obs_age)
        return sts, (round(statistics.median(obs_ages)) if obs_ages else None)

    return _cached("stations", fetch)


def forecast_age_min():
    """Minutes since the hourly job last wrote forecasts. This is not the age of the air readings."""
    rows = db.select("forecasts_latest", select="generated_at", order="generated_at.desc", limit=1)
    return round((datetime.now(timezone.utc) - _ts(rows[0]["generated_at"])).total_seconds() / 60) if rows else None


def snapshot_info():
    """Capture time of the frozen demo snapshot, shown in the interface instead of a data age."""
    snap = db.select("route_cache", select="response", key="eq.snapshot:stations")[0]["response"]
    return {"captured_at": snap["captured_at"], "data_age_at_capture_min": snap["data_age_at_capture_min"]}


def geocode(q):
    k = q.strip().lower()
    if k in PLACES:
        return PLACES[k]
    hit = db.select("route_cache", select="response", key=f"eq.geo:{k}")
    if hit:
        return tuple(hit[0]["response"])
    wait = 1.1 - (time.time() - _LAST_GEO[0])   # Nominatim allows about 1 request per second
    if wait > 0:
        time.sleep(wait)
    _LAST_GEO[0] = time.time()
    r = httpx.get("https://nominatim.openstreetmap.org/search", timeout=6,
                  params={"q": q + ", Delhi", "format": "jsonv2", "limit": 1, "countrycodes": "in"},
                  headers={"User-Agent": f"AirGuard-hackathon/0.1 ({cfg()['CONTACT_EMAIL']})"})   # Nominatim requires a contact
    r.raise_for_status()
    if not r.json():
        raise ValueError(f"Could not find '{q}'")
    pt = [float(r.json()[0]["lat"]), float(r.json()[0]["lon"])]
    db.upsert("route_cache", [{"key": f"geo:{k}", "response": pt}], "key")
    return tuple(pt)


def get_routes(o_lat, o_lon, d_lat, d_lon, mode):
    key = hashlib.sha1(f"{mode}:{o_lat:.4f},{o_lon:.4f}>{d_lat:.4f},{d_lon:.4f}".encode()).hexdigest()
    hit = db.select("route_cache", select="response", key=f"eq.{key}")
    if hit:
        return hit[0]["response"]
    body = {"coordinates": [[o_lon, o_lat], [d_lon, d_lat]], "instructions": False,
            "alternative_routes": {"target_count": 3, "share_factor": 0.6, "weight_factor": 1.6}}
    url, headers = f"{ORS}/{MODES[mode]['ors_profile']}/geojson", {"Authorization": cfg()["ORS_API_KEY"]}
    r = httpx.post(url, json=body, headers=headers, timeout=8)   # fail fast: the Lambda limit is 29 s
    if r.status_code == 400:  # for example a route over 100 km: retry without alternatives
        body.pop("alternative_routes")
        r = httpx.post(url, json=body, headers=headers, timeout=8)
    r.raise_for_status()
    routes = [{"id": f"r{i + 1}", "coords": [[round(x, 5), round(y, 5)] for x, y in f["geometry"]["coordinates"]],
               "duration_s": f["properties"]["summary"]["duration"], "distance_m": f["properties"]["summary"]["distance"]}
              for i, f in enumerate(r.json()["features"])]
    if not routes:
        raise ValueError("No route found between those places.")
    db.upsert("route_cache", [{"key": key, "response": routes}], "key")
    return routes


def score_trip(o, d, mode, depart_in_h=0.0, demo=False):
    stations, age = load_stations(demo)
    routes = get_routes(o["lat"], o["lon"], d["lat"], d["lon"], mode)
    scored = [{"id": r["id"], **score_route(r["coords"], r["duration_s"], mode, depart_in_h, stations), "geometry": r["coords"]}
              for r in routes]
    cleanest = min(scored, key=lambda x: x["exposure_index"])["id"]
    fastest = min(scored, key=lambda x: x["duration_min"])["id"]
    for s in scored:
        s["is_cleanest"], s["is_fastest"] = s["id"] == cleanest, s["id"] == fastest
    return {"routes": scored, "data_age_min": age, "mode_factor": MODES[mode]["factor"]}


def departure(o, d, mode, earliest_in_h=0.0, window_h=4.0, max_wait_min=120, demo=False,
              sensitivity="normal", max_extra_min=15):
    stations, age = load_stations(demo)
    routes = get_routes(o["lat"], o["lon"], d["lat"], d["lon"], mode)
    res = best_departure(routes, mode, stations, earliest_in_h, window_h, max_wait_min,
                         sensitivity=sensitivity, max_extra_min=max_extra_min)
    res["data_age_min"] = age
    return res


def analyze_trip(o, d, mode, demo=False, window_h=4.0, max_wait_min=120, sensitivity="normal", max_extra_min=15):
    """The planner's single entry point: routes plus departure advice in one call.
    Stores a compact summary under a trip id so the agent can explain it without recomputing."""
    res = score_trip(o, d, mode, 0.0, demo)
    dep = departure(o, d, mode, 0.0, window_h, max_wait_min, demo, sensitivity, max_extra_min)
    keep = ("id", "duration_min", "distance_km", "exposure_index", "mean_pm25", "risk", "confidence", "is_cleanest", "is_fastest")
    by_wait = {}
    for opt in dep["options"]:
        w = opt["wait_min"]
        if w % 30 == 0 and (w not in by_wait or opt["exposure_index"] < by_wait[w]["exposure_index"]):
            by_wait[w] = opt
    summary = {"mode": mode, "demo": demo, "routes": [{k: r[k] for k in keep} for r in res["routes"]],
               "baseline": dep["baseline"], "recommended": dep["recommended"], "delta": dep["delta"],
               "best_by_wait": list(by_wait.values()), "data_age_min": res["data_age_min"], "preference": dep["preference"],
               "snapshot": snapshot_info() if demo else None}
    trip_id = hashlib.sha1(json.dumps([o, d, mode, demo, sensitivity, max_extra_min, max_wait_min, round(time.time() / 3600)], sort_keys=True).encode()).hexdigest()[:16]
    db.upsert("route_cache", [{"key": f"trip:{trip_id}", "response": summary}], "key")
    return {"trip_id": trip_id, "routes": res, "departure": dep, "snapshot": snapshot_info() if demo else None}


def forecast_at(lat, lon, horizon_h, demo=False):
    stations, age = load_stations(demo)
    pm, lo, hi, d = idw(lat, lon, stations, horizon_h)
    return {"pm25": round(pm, 1), "low": round(lo, 1), "high": round(hi, 1), "nearest_station_km": round(d, 1), "data_age_min": age}


def eval_metrics():
    return db.select("eval_metrics", select="*", model_version=f"eq.{cfg().get('MODEL_VERSION', 'v1')}", order="horizon_h.asc")   # only the deployed model version
```

**`api/main.py`**

```python
import os
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from pydantic import BaseModel, Field

from api import service

app = FastAPI(title="AirGuard API", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])
Mode = Literal["walk", "cycle", "car"]
Sensitivity = Literal["normal", "sensitive", "high"]


class Point(BaseModel):
    lat: float = Field(ge=28.2, le=29.0)   # Delhi NCR box for v1
    lon: float = Field(ge=76.7, le=77.7)


class TripRequest(BaseModel):
    origin: Point
    destination: Point
    mode: Mode = "walk"
    max_extra_min: int = Field(15, ge=0, le=120)
    max_wait_min: int = Field(120, ge=0, le=720)
    sensitivity: Sensitivity = "normal"
    demo: bool = False


class DepartureRequest(BaseModel):
    origin: Point
    destination: Point
    mode: Mode = "walk"
    window_h: float = Field(4.0, gt=0, le=6)
    max_wait_min: int = Field(120, ge=0, le=720)
    max_extra_min: int = Field(15, ge=0, le=120)
    sensitivity: Sensitivity = "normal"
    demo: bool = False


class Segment(BaseModel):
    lat: float
    lon: float
    pm25: float
    minutes: float
    line: list[list[float]]


class RouteOut(BaseModel):
    id: str
    duration_min: float
    distance_km: float
    exposure_index: float
    mean_pm25: float
    risk: str
    confidence: float
    segments: list[Segment]
    geometry: list[list[float]]
    is_cleanest: bool
    is_fastest: bool


class TripResponse(BaseModel):
    routes: list[RouteOut]
    data_age_min: int | None
    mode_factor: float


def err(status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(RequestValidationError)
async def _validation(_, exc):
    return err(422, "invalid_input", str(exc.errors()[0]["msg"]))


@app.exception_handler(HTTPException)
async def _http(_, exc):
    return err(exc.status_code, "error", str(exc.detail))


@app.exception_handler(ValueError)
async def _no_data(_, exc):
    return err(503, "no_data", str(exc))


@app.exception_handler(httpx.HTTPError)
async def _upstream(_, exc):
    return err(502, "upstream_unavailable", "A data provider is not responding. Try again shortly.")


@app.get("/health")
def health():
    stations, age = service.load_stations()
    return {"status": "ok" if stations else "no_data", "stations": len(stations), "observation_age_min": age,
            "forecast_age_min": service.forecast_age_min()}


@app.get("/geocode")
def geocode(q: str = Query(min_length=2, max_length=80)):
    try:
        lat, lon = service.geocode(q)
    except ValueError as e:
        raise HTTPException(404, str(e))
    if not (28.2 <= lat <= 29.0 and 76.7 <= lon <= 77.7):
        raise HTTPException(422, "That place is outside Delhi NCR, the only area supported.")
    return {"lat": lat, "lon": lon}


@app.get("/forecast")
def forecast(lat: float = Query(ge=28.2, le=29.0), lon: float = Query(ge=76.7, le=77.7),
             horizon_h: float = Query(1, ge=0, le=24), demo: bool = False):
    return service.forecast_at(lat, lon, horizon_h, demo)


@app.post("/routes/score", response_model=TripResponse)
def routes_score(req: TripRequest):
    return service.score_trip(req.origin.model_dump(), req.destination.model_dump(), req.mode, 0.0, req.demo)


@app.post("/trips/analyze")
def trips_analyze(req: TripRequest):
    return service.analyze_trip(req.origin.model_dump(), req.destination.model_dump(), req.mode, req.demo,
                                max_wait_min=req.max_wait_min, sensitivity=req.sensitivity, max_extra_min=req.max_extra_min)


@app.post("/departure/best")
def departure_best(req: DepartureRequest):
    return service.departure(req.origin.model_dump(), req.destination.model_dump(), req.mode,
                             0.0, req.window_h, req.max_wait_min, req.demo,
                             req.sensitivity, req.max_extra_min)


@app.get("/config")
def config():
    from engine.exposure import MODES, level_config
    return {"levels": level_config(), "mode_factors": {k: v["factor"] for k, v in MODES.items()}}


@app.get("/eval")
def eval_():
    return service.eval_metrics()


handler = Mangum(app, lifespan="off")
```

Run it locally with `uvicorn api.main:app --reload --port 8000` and open `http://localhost:8000/docs` to try each endpoint.

**`infra/Dockerfile`** (build context is the repo root):

```dockerfile
FROM public.ecr.aws/lambda/python:3.12
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r requirements.txt
COPY common ${LAMBDA_TASK_ROOT}/common
COPY engine ${LAMBDA_TASK_ROOT}/engine
COPY api ${LAMBDA_TASK_ROOT}/api
COPY agent ${LAMBDA_TASK_ROOT}/agent
COPY ingestion ${LAMBDA_TASK_ROOT}/ingestion
COPY ml ${LAMBDA_TASK_ROOT}/ml
CMD ["api.main.handler"]
```

**`infra/template.yaml`**

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Transform: AWS::Serverless-2016-10-31
Description: AirGuard

Parameters:
  AllowedOrigins:
    Type: String
    Default: "*"          # set to your frontend URL after the first deploy
  ModelBucket:
    Type: String
  ModelVersion:
    Type: String
    Default: v1

Globals:
  Function:
    PackageType: Image
    Architectures: [x86_64]
    MemorySize: 1024
    Timeout: 29              # API Gateway HTTP APIs cap an integration at 30 seconds
    Environment:
      Variables:
        ALLOWED_ORIGINS: !Ref AllowedOrigins
        MODEL_VERSION: !Ref ModelVersion
        LLM_BACKEND: bedrock
        BEDROCK_MODEL_ID: amazon.nova-2-lite-v1:0

Resources:
  HttpApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      DefaultRouteSettings:
        ThrottlingBurstLimit: 20
        ThrottlingRateLimit: 10
      RouteSettings:
        "POST /agent/chat":      # protects your credits from a runaway client
          ThrottlingBurstLimit: 3
          ThrottlingRateLimit: 1

  ApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      ImageConfig:
        Command: ["api.main.handler"]
      Policies:
        - SSMParameterReadPolicy:
            ParameterName: airguard/*
      Events:
        Any:
          Type: HttpApi
          Properties:
            ApiId: !Ref HttpApi
            Path: /{proxy+}
            Method: ANY
    Metadata:
      Dockerfile: infra/Dockerfile
      DockerContext: ../
      DockerTag: v1

  AgentFunction:
    Type: AWS::Serverless::Function
    Properties:
      ImageConfig:
        Command: ["agent.handler.lambda_handler"]
      Policies:
        - SSMParameterReadPolicy:
            ParameterName: airguard/*
        - Statement:
            - Effect: Allow
              Action: [bedrock:InvokeModel, bedrock:InvokeModelWithResponseStream]
              Resource: "*"        # narrow to your model's ARN once it works
      Events:
        Chat:
          Type: HttpApi
          Properties:
            ApiId: !Ref HttpApi
            Path: /agent/chat
            Method: POST
    Metadata:
      Dockerfile: infra/Dockerfile
      DockerContext: ../
      DockerTag: v1

  IngestFunction:
    Type: AWS::Serverless::Function
    Properties:
      Timeout: 300
      ImageConfig:
        Command: ["ingestion.handler.lambda_handler"]
      Policies:
        - SSMParameterReadPolicy:
            ParameterName: airguard/*
        - S3ReadPolicy:
            BucketName: !Ref ModelBucket
      Events:
        Hourly:
          Type: Schedule
          Properties:
            Schedule: rate(1 hour)
    Metadata:
      Dockerfile: infra/Dockerfile
      DockerContext: ../
      DockerTag: v1

Outputs:
  ApiUrl:
    Value: !Sub "https://${HttpApi}.execute-api.${AWS::Region}.${AWS::URLSuffix}/"
```

The agent's route (`POST /agent/chat`) is more specific than the API's catch-all, so API Gateway sends chat requests to the agent function. CORS is handled in code only (FastAPI's middleware and the agent handler's headers), to avoid duplicate headers from two layers. Upstream calls use short timeouts (routing 8 seconds, geocoding 6, database 10) so a slow free API fails fast with a clear message instead of outliving the 29-second Lambda limit; pre-cache the demo routes.

**Deploy**

```bash
sam validate -t infra/template.yaml
sam build -t infra/template.yaml
sam deploy --guided --stack-name airguard --region us-east-1 \
  --resolve-image-repos --capabilities CAPABILITY_IAM \
  --parameter-overrides ModelBucket=airguard-models-<your-suffix> ModelVersion=$MODEL_VERSION   # the version you uploaded in Appendix D

# smoke tests
API=$(aws cloudformation describe-stacks --stack-name airguard \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
curl ${API}health
aws lambda invoke --function-name <IngestFunction name from the stack> /tmp/out.json && cat /tmp/out.json
```

The first `sam deploy` creates the container registry repository for you and saves your choices to `samconfig.toml`; later deploys are just `sam build && sam deploy`.

**Troubleshooting**

| Symptom | Likely cause and fix |
| --- | --- |
| `AccessDenied` reading SSM parameters | The parameter names must start with `/airguard/`; if the error mentions decryption, add `kms:Decrypt` to the role |
| 504 from the agent route | The 30-second API Gateway limit; reduce tool calls, use the smaller model, or serve the cached answer |
| `/health` shows 0 stations | The ingestion job hasn't run yet or the `forecasts_latest` table is empty; invoke the ingestion Lambda once by hand |
| Slow first request | Cold start of a large image; invoke it once before the demo and cache the demo trips |
| Build fails on an Apple Silicon Mac | Make sure Docker is running and building for `linux/amd64`; expect a slower build |
| Charges worry you | Check the Billing page and the Budgets alert; delete the stack and the registry repository after judging |

## Appendix G: Strands agent, tools, and system prompt

The agent calls the same service functions the API uses, in-process, so it never invents numbers. Install notes from the Strands quickstart: Python 3.10 or newer, `pip install strands-agents`, tools are plain Python functions decorated with `@tool` whose docstring tells the model what they do, and models come from `strands.models` (`BedrockModel`, or `OllamaModel` via the `strands-agents[ollama]` extra). I could not open the Bedrock provider page for exact constructor options, so confirm `BedrockModel`'s parameters in the current Strands docs when you wire it up.

In v1 the user's profile (sensitivity and usual mode) comes from the browser in each request instead of a database tool, and the agent can ask a tool for the current time (the snapshot's capture time in demo mode) so it can say which clock time a recommended wait corresponds to.

**`agent/tools.py`**

```python
import json
import os
from datetime import datetime, timedelta, timezone

from strands import tool

from api import service
from common import db
from engine.exposure import MODES

STATE = {"demo": False}          # set per request by the handler
IST = timezone(timedelta(hours=5, minutes=30))


def _j(x):
    return json.dumps(x, separators=(",", ":"))


def _check(lat, lon, mode="walk"):
    if not (28.2 <= lat <= 29.0 and 76.7 <= lon <= 77.7):
        raise ValueError("Only Delhi NCR is supported.")
    if mode not in MODES:
        raise ValueError("Mode must be walk, cycle or car.")


@tool
def now_ist() -> str:
    """Get the current date and time in India Standard Time, to say which clock time a recommended wait corresponds to."""
    if STATE["demo"]:   # frozen snapshot: its capture time is the clock
        t = datetime.fromisoformat(service.snapshot_info()["captured_at"]).astimezone(IST)
        return _j({"now": t.isoformat(timespec="minutes"), "weekday": t.strftime("%A"), "note": "frozen demo snapshot"})
    n = datetime.now(IST)
    return _j({"now": n.isoformat(timespec="minutes"), "weekday": n.strftime("%A")})


@tool
def geocode(place: str) -> str:
    """Find the latitude and longitude of a place in Delhi NCR.

    Args:
        place: A landmark, neighbourhood or address, for example 'Hauz Khas'.
    """
    try:
        lat, lon = service.geocode(place)
        return _j({"place": place, "lat": lat, "lon": lon})
    except Exception as e:
        return _j({"error": str(e)})


@tool
def get_forecast(lat: float, lon: float, hours_ahead: float = 1.0) -> str:
    """Forecast PM2.5 in micrograms per cubic metre at a point, with a low-high range and the distance to the nearest station.

    Args:
        lat: Latitude.
        lon: Longitude.
        hours_ahead: Hours from now, between 0 and 24.
    """
    try:
        _check(lat, lon)
        return _j(service.forecast_at(lat, lon, min(max(hours_ahead, 0), 24), STATE["demo"]))
    except Exception as e:
        return _j({"error": str(e)})


@tool
def score_routes(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float,
                 mode: str = "walk") -> str:
    """Compare alternative routes for a trip by estimated pollution exposure.

    Args:
        origin_lat: Origin latitude.
        origin_lon: Origin longitude.
        dest_lat: Destination latitude.
        dest_lon: Destination longitude.
        mode: One of walk, cycle, car.
    """
    try:
        _check(origin_lat, origin_lon, mode); _check(dest_lat, dest_lon, mode)
        res = service.score_trip({"lat": origin_lat, "lon": origin_lon}, {"lat": dest_lat, "lon": dest_lon},
                                 mode, 0.0, STATE["demo"])
        keep = ("id", "duration_min", "distance_km", "exposure_index", "mean_pm25", "risk", "confidence", "is_cleanest", "is_fastest")
        return _j({"routes": [{k: r[k] for k in keep} for r in res["routes"]], "data_age_min": res["data_age_min"],
                   "note": "exposure_index is a relative index for comparing options, not a measured dose"})
    except Exception as e:
        return _j({"error": str(e)})


@tool
def best_departure_time(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float,
                        mode: str = "walk", window_hours: float = 4.0, max_wait_minutes: int = 120,
                        sensitivity: str = "normal", max_extra_minutes: int = 15) -> str:
    """Find the departure time that minimises estimated exposure, within a maximum wait.

    Args:
        origin_lat: Origin latitude.
        origin_lon: Origin longitude.
        dest_lat: Destination latitude.
        dest_lon: Destination longitude.
        mode: One of walk, cycle, car.
        window_hours: How many hours ahead to search, up to 6.
        max_wait_minutes: The longest the user is willing to wait before leaving.
        sensitivity: One of normal, sensitive, high, from the profile line.
        max_extra_minutes: The most extra total minutes the user will accept.
    """
    try:
        _check(origin_lat, origin_lon, mode); _check(dest_lat, dest_lon, mode)
        res = service.departure({"lat": origin_lat, "lon": origin_lon}, {"lat": dest_lat, "lon": dest_lon}, mode,
                                0.0, min(max(window_hours, 0.25), 6), max_wait_minutes, STATE["demo"],
                                sensitivity, max_extra_minutes)
        by_wait = {}
        for o in res["options"]:
            if o["wait_min"] % 30 == 0 and (o["wait_min"] not in by_wait or o["exposure_index"] < by_wait[o["wait_min"]]["exposure_index"]):
                by_wait[o["wait_min"]] = o
        return _j({"baseline": res["baseline"], "recommended": res["recommended"], "delta": res["delta"], "preference": res["preference"],
                   "best_by_wait": list(by_wait.values()), "data_age_min": res["data_age_min"]})
    except Exception as e:
        return _j({"error": str(e)})


@tool
def get_trip_result(trip_id: str) -> str:
    """Read the saved result for the trip the user is looking at: routes, the recommended route, and the best departure time, already computed.

    Args:
        trip_id: The id from the '[Current trip id: ...]' line at the start of the message.
    """
    hit = db.select("route_cache", select="response", key=f"eq.trip:{trip_id}")
    return _j(hit[0]["response"]) if hit else _j({"error": "Trip result not found. Ask the user to run Compare routes again."})


TOOLS = [now_ist, get_trip_result, geocode, get_forecast, score_routes, best_departure_time]

if os.environ.get("ALERT_TOPIC_ARN"):   # optional: email a summary through SNS (see the snippet below)
    @tool
    def send_email_summary(subject: str, body: str) -> str:
        """Email the user a short summary of the recommendation.

        Args:
            subject: Email subject, under 80 characters.
            body: Plain-text body, under 800 characters.
        """
        import boto3
        boto3.client("sns").publish(TopicArn=os.environ["ALERT_TOPIC_ARN"], Subject=subject[:99], Message=body[:2000])
        return _j({"sent": True})

    TOOLS.append(send_email_summary)
```

For the optional email tool, add this to `template.yaml`, add `SNSPublishMessagePolicy: {TopicName: !GetAtt AlertTopic.TopicName}` to the agent's policies, set `ALERT_TOPIC_ARN: !Ref AlertTopic` in its environment, and subscribe your address (the subscriber must confirm by email):

```yaml
  AlertTopic:
    Type: AWS::SNS::Topic
```

**`agent/agent.py`**

```python
import os

from strands import Agent
from strands.models import BedrockModel

from agent.tools import STATE, TOOLS

SYSTEM_PROMPT = """You are AirGuard, a trip assistant that helps people in Delhi NCR choose routes and departure times that lower their exposure to PM2.5 air pollution.

Rules:
1. Every number you state (PM2.5, minutes, exposure index, percentages) must come from a tool result in this conversation. Never estimate or recall numbers from memory. If you lack a number, call a tool or say you cannot tell.
2. If the message starts with a '[Current trip id: ...]' line, call get_trip_result first and answer from it; do not recompute that trip. To compare routes for a different trip call score_routes. To suggest when to leave call best_departure_time. Call geocode first when the user names places. Scheduled departure times are not supported in v1: AirGuard compares leaving now with waiting and leaving later, within the next few hours. If the user names a specific later time, say so and answer for leaving now versus waiting. Use now_ist only to say which clock time a recommended wait corresponds to. In a frozen demo snapshot, now_ist returns the snapshot's capture time, so give waits as minutes after that time.
3. Exposure is an index for comparing options under stated assumptions, not a measured dose. Say 'estimated exposure' and express differences as percentages between options. Never describe a level as an official AQI category.
4. Always mention the reliability score and the data age in plain words. If the trip result says it comes from a demo snapshot, say it is a frozen snapshot captured at the stated time, not live data. If reliability is below 0.5 or data_age_min is above 180, say the estimate is uncertain and why.
5. The recommendation comes from the tool's decision rule, which uses the profile's sensitivity and the user's limits on extra minutes and waiting. Report the recommended option, its time cost in minutes, and the limits that were used; never pick a different option yourself.
6. Adapt to the profile line at the start of the message. For sensitivity 'sensitive' or 'high', pass the sensitivity to best_departure_time (it changes how much extra time the decision rule accepts, never the exposure estimate) and note that general guidance is to limit hard exertion outdoors on high-pollution days. Do not diagnose, give medical advice, or mention medication; suggest a doctor for health concerns.
7. Keep answers short: a one-line recommendation first, then at most four bullets with the numbers behind it. No tables.
8. If a tool returns an error, say in one sentence what failed and what the user can try.
9. Only Delhi NCR and the modes walk, cycle and car are supported."""


def make_model():
    if os.environ.get("LLM_BACKEND", "bedrock") == "ollama":
        from strands.models.ollama import OllamaModel
        return OllamaModel(host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
                           model_id=os.environ.get("OLLAMA_MODEL", "llama3.1"))
    return BedrockModel(model_id=os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-2-lite-v1:0"),
                        region_name=os.environ.get("AWS_REGION", "us-east-1"), temperature=0.2)


def trace(messages):
    """Pull tool calls and their results out of the conversation messages (Converse-style content blocks)."""
    calls = {}
    for m in messages:
        for block in m.get("content", []):
            if "toolUse" in block:
                tu = block["toolUse"]
                calls[tu["toolUseId"]] = {"name": tu["name"], "input": tu["input"], "output": None}
            elif "toolResult" in block:
                tr = block["toolResult"]
                text = " ".join(c.get("text", "") for c in tr.get("content", []))
                if tr["toolUseId"] in calls:
                    calls[tr["toolUseId"]]["output"] = text[:2000]
    return list(calls.values())


def chat(message, profile=None, history=None, demo=False, trip_id=None):
    STATE["demo"] = demo
    ctx = ""
    if profile:
        ctx = f"[Profile: sensitivity={profile.get('sensitivity', 'normal')}, usual mode={profile.get('mode', 'walk')}]\n"
    if trip_id:
        ctx += f"[Current trip id: {trip_id}]\n"
    agent = Agent(model=make_model(), system_prompt=SYSTEM_PROMPT, tools=TOOLS, callback_handler=None,
                  messages=history or [])
    start = len(agent.messages)
    result = agent(ctx + message)
    return {"answer": str(result), "tool_calls": trace(agent.messages[start:]), "cached": False}
```

A new agent is created for each request, so warm Lambda containers never share conversation state. If `trace()` returns nothing, print `agent.messages` once and adjust the block names to match what your Strands version produces.

**`agent/handler.py`**

```python
import hashlib
import json
import os

from agent.agent import chat
from common import db


def _resp(code, body, origin):
    allowed = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
    allow = "*" if "*" in allowed else (origin if origin in allowed else allowed[0])
    return {"statusCode": code, "headers": {"content-type": "application/json", "access-control-allow-origin": allow},
            "body": json.dumps(body)}


def _cached(msg):
    key = "agent:" + hashlib.sha1(msg.strip().lower().encode()).hexdigest()
    hit = db.select("route_cache", select="response", key=f"eq.{key}")
    return hit[0]["response"] if hit else None


def _history(items):
    return [{"role": h["role"], "content": [{"text": h["text"][:1000]}]} for h in items
            if h.get("role") in ("user", "assistant") and h.get("text")]


def lambda_handler(event, context):
    origin = (event.get("headers") or {}).get("origin", "")
    body = json.loads(event.get("body") or "{}")
    msg = (body.get("message") or "").strip()
    if not 1 <= len(msg) <= 500:
        return _resp(400, {"error": {"code": "invalid_input", "message": "Message must be 1 to 500 characters."}}, origin)
    try:
        out = chat(msg, body.get("profile"), _history(body.get("history", [])[-6:]), bool(body.get("demo")), body.get("trip_id"))
        return _resp(200, out, origin)
    except Exception as e:            # model, tool or network failure
        print("agent failed:", repr(e))
        hit = _cached(msg) if body.get("demo") else None   # saved answers exist only for the frozen demo scenario
        if hit:
            return _resp(200, {**hit, "cached": True}, origin)
        return _resp(503, {"error": {"code": "agent_unavailable",
                                     "message": "The assistant is unavailable right now. The route and departure results still work."}}, origin)
```

**Test in this order**

1. With Ollama, no AWS needed: `LOCAL=1 LLM_BACKEND=ollama python -c "from agent.agent import chat; print(chat('I cycle from Hauz Khas to DU North Campus right now. Should I leave now or wait, and which route?', {'sensitivity': 'sensitive', 'mode': 'cycle'}))"`
2. Confirm `tool_calls` shows `two geocode calls, score_routes, and best_departure_time (now_ist is optional)`, and that every number in the answer appears in a tool output.
3. Switch to Bedrock: `LLM_BACKEND=bedrock` with AWS credentials, region `us-east-1`. Fix any access error in the Bedrock console first (Appendix K).
4. Try bad inputs: a place outside Delhi, `mode="bus"`, and a departure 20 hours away. The agent should explain the limit instead of guessing.

**Follow-up check.** Run Compare routes in the app (or call `POST /trips/analyze`), copy the returned `trip_id`, and ask the agent "Why route 2?" with that id. The tool trace should show only `get_trip_result`, with no geocoding or routing calls, and the answer should arrive in a few seconds. This is the path to rehearse for the live demo.

**Expected shape of a good answer** (the numbers are placeholders; real ones come from the tools):

> Take route r2 and leave about 40 minutes later: estimated exposure is X% lower for Y extra minutes in total.
>
> - r2 is Z minutes longer than the fastest route but its average PM2.5 is lower.
> - Leaving later moves most of the trip into a cleaner hour.
> - Reliability is 0.NN and the data is N minutes old, so treat this as a good estimate, not a guarantee.
> - General guidance: if you are sensitive to air pollution, avoid hard exertion on high-pollution days.

## Appendix H: Frontend pages, components, and code

The frontend is a client-side Next.js app (static export) with MapLibre for the map and Recharts for charts. It has three pages: the planner (home), an evaluation page that shows the backtest, and an about page that states assumptions and attributions.

| Page or component | Job | Notes |
| --- | --- | --- |
| `/` planner | Origin, destination, mode, sensitivity, demo toggle; shows routes, the departure chart, and the chat | The main demo screen |
| `RouteMap` | Draws each route; colours segments by forecast PM2.5 | Selected route is thicker; legend and risk text so colour is not the only signal |
| `RouteCards` | Per-route duration, extra minutes, exposure index, difference vs the fastest, average PM2.5, risk, reliability | Click to select |
| `DepartureChart` | Exposure index by waiting time, with the recommended time stated in a sentence and a caption: "forecasts at five horizons, interpolated to 15-minute steps" | Uses real numbers from `/departure/best` |
| `ChatPanel` | Agent conversation; each reply has a "Tools used" section with inputs and outputs | This is what proves the agent calls tools |
| `/eval` | Backtest table and a bar chart of error per horizon for the model and both baselines | Your credibility page |
| `/about` | Mode factors, risk bands, reliability formula, data sources, limits, attributions, disclaimer | Read the levels from the API's /config endpoint and reuse Appendix E's constants table for the wording; say that data reliability is a heuristic score, not a probability, and call the forecast range calibrated only if the evaluation page's coverage supports it |

**The geocode endpoint lives in `api/main.py`**, so the browser can resolve place names. It is already in the Appendix F listing, so there is nothing to add; here is its test:

```python
# tests/test_api.py
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_geocode_known_place_returns_lat_lon():
    r = client.get("/geocode", params={"q": "hauz khas"})   # a built-in landmark, so no network call
    assert r.status_code == 200
    assert set(r.json()) == {"lat", "lon"}


def test_geocode_rejects_a_too_short_query():
    assert client.get("/geocode", params={"q": "a"}).status_code == 422
```

**`frontend/next.config.ts`** (static export, so Amplify only serves files):

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = { output: "export" };
export default nextConfig;
```

**`frontend/src/lib/api.ts`**

```ts
const API = process.env.NEXT_PUBLIC_API_URL!;

export type Mode = "walk" | "cycle" | "car";
export type Pt = { lat: number; lon: number };
export type Segment = { lat: number; lon: number; pm25: number; minutes: number; line: number[][] };
export type Route = {
  id: string; duration_min: number; distance_km: number; exposure_index: number; mean_pm25: number;
  risk: string; confidence: number; segments: Segment[]; geometry: number[][];
  is_cleanest: boolean; is_fastest: boolean;
};
export type ToolCall = { name: string; input: unknown; output: string | null };
export type EvalRow = {
  horizon_h: number; mae: number; rmse: number;
  baseline_persistence_mae: number; baseline_hourly_mean_mae: number; n_samples: number;
  model_version: string; interval_coverage: number | null; interval_width: number | null;
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(API + path, { headers: { "content-type": "application/json" }, ...init });
  const j = await r.json();
  if (!r.ok) throw new Error(j?.error?.message ?? "Request failed");
  return j as T;
}
const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const geocode = (q: string) => call<Pt>(`/geocode?q=${encodeURIComponent(q)}`);
export const scoreRoutes = (b: unknown) =>
  call<{ routes: Route[]; data_age_min: number | null; mode_factor: number }>("/routes/score", post(b));
export const bestDeparture = (b: unknown) => call<any>("/departure/best", post(b));
export const analyzeTrip = (b: unknown) =>
  call<{ trip_id: string; routes: { routes: Route[]; data_age_min: number | null; mode_factor: number }; departure: any; snapshot: { captured_at: string; data_age_at_capture_min: number | null } | null }>("/trips/analyze", post(b));
export const chat = (b: unknown) =>
  call<{ answer: string; tool_calls: ToolCall[]; cached: boolean }>("/agent/chat", post(b));
export const evalMetrics = () => call<EvalRow[]>("/eval");
export type Level = { name: string; max: number | null; color: string };
export const getConfig = () => call<{ levels: Level[]; mode_factors: Record<string, number> }>("/config");
```

**`frontend/src/components/RouteMap.tsx`**

```tsx
"use client";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { Level, Route } from "@/lib/api";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const colorExpr = (levels: Level[]): any => ["step", ["get", "pm25"], levels[0].color, ...levels.slice(0, -1).flatMap((l, i) => [(l.max as number) + 1e-6, levels[i + 1].color])];

export default function RouteMap({ routes, selected, levels }: { routes: Route[]; selected: string | null; levels: Level[] }) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    const m = new maplibregl.Map({
      container: box.current!, style: process.env.NEXT_PUBLIC_MAP_STYLE_URL!, center: [77.209, 28.614], zoom: 10.5,
    });
    m.addControl(new maplibregl.NavigationControl(), "top-right");
    map.current = m;
    return () => { m.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const draw = () => {
      (m.getStyle()?.layers ?? []).filter((l) => l.id.startsWith("rt-")).forEach((l) => m.removeLayer(l.id));
      Object.keys(m.getStyle()?.sources ?? {}).filter((s) => s.startsWith("rt-")).forEach((s) => m.removeSource(s));
      const bounds = new maplibregl.LngLatBounds();
      for (const r of routes) {
        const on = r.id === selected;
        r.geometry.forEach(([x, y]) => bounds.extend([x, y]));
        m.addSource(`rt-${r.id}-base`, { type: "geojson", data: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: r.geometry } } });
        m.addLayer({ id: `rt-${r.id}-base`, type: "line", source: `rt-${r.id}-base`, paint: { "line-color": "#ffffff", "line-width": on ? 9 : 6, "line-opacity": on ? 0.95 : 0.6 } });
        const features = r.segments.filter((s) => s.line.length > 1).map((s) => ({ type: "Feature" as const, properties: { pm25: s.pm25 }, geometry: { type: "LineString" as const, coordinates: s.line } }));   // each piece follows the real road
        m.addSource(`rt-${r.id}-seg`, { type: "geojson", data: { type: "FeatureCollection", features } });
        m.addLayer({ id: `rt-${r.id}-seg`, type: "line", source: `rt-${r.id}-seg`, paint: { "line-color": colorExpr(levels), "line-width": on ? 5 : 3, "line-opacity": on ? 1 : 0.55 } });
      }
      if (!bounds.isEmpty()) m.fitBounds(bounds, { padding: 60, duration: 600 });
    };
    if (m.isStyleLoaded()) draw(); else m.once("load", draw);
  }, [routes, selected, levels]);

  return <div ref={box} className="h-full min-h-[360px] w-full rounded-lg" />;
}
```

**`frontend/src/components/RouteCards.tsx`**

```tsx
import type { Route } from "@/lib/api";

export default function RouteCards({ routes, selected, onSelect }: { routes: Route[]; selected: string | null; onSelect: (id: string) => void }) {
  const fastest = routes.find((r) => r.is_fastest) ?? routes[0];
  return (
    <div className="space-y-2">
      {routes.map((r) => {
        const extra = r.duration_min - fastest.duration_min;
        const pct = fastest.exposure_index ? ((r.exposure_index - fastest.exposure_index) / fastest.exposure_index) * 100 : 0;
        return (
          <button key={r.id} onClick={() => onSelect(r.id)}
            className={`w-full rounded-lg border p-3 text-left ${selected === r.id ? "border-blue-600 ring-1 ring-blue-600" : "border-gray-300"}`}>
            <div className="flex justify-between">
              <span className="font-medium">Route {r.id.slice(1)}</span>
              <span className="text-xs">{r.is_cleanest && "Lowest exposure"} {r.is_fastest && "· Fastest"}</span>
            </div>
            <div className="mt-1 text-sm">{r.duration_min} min ({extra > 0 ? `+${extra.toFixed(0)} min` : "fastest"}) · {r.distance_km} km</div>
            <div className="text-sm">Exposure index {r.exposure_index.toFixed(0)} ({Math.abs(pct) < 0.5 ? "baseline" : `${pct > 0 ? "+" : ""}${pct.toFixed(0)}% vs fastest`})</div>
            <div className="text-xs text-gray-600">Average PM2.5 {r.mean_pm25} µg/m³ · AirGuard level: {r.risk.replace("_", " ")} · data reliability {r.confidence}</div>
          </button>
        );
      })}
    </div>
  );
}
```

**`frontend/src/components/DepartureChart.tsx`**

```tsx
import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default function DepartureChart({ dep }: { dep: any }) {
  const best: Record<number, number> = {};
  for (const o of dep.options) best[o.wait_min] = Math.min(best[o.wait_min] ?? Infinity, o.exposure_index);
  const data = Object.entries(best).map(([w, d]) => ({ wait: Number(w), exposure_index: Math.round(d) }));
  const pct = dep.delta.exposure_index_pct as number;
  const rec = dep.recommended;
  const same = Math.abs(pct) < 0.5 && dep.delta.arrival_min === 0;
  const msg = same
    ? "The fastest route leaving now is already the best choice for your settings."
    : `Take route ${String(rec.route_id).slice(1)}${rec.wait_min ? `, leaving ${rec.wait_min} min later` : ""}: estimated exposure ${Math.abs(pct)}% ${pct < 0 ? "lower" : "higher"}, arriving ${dep.delta.arrival_min} min later.`;
  return (
    <div>
      <p className="text-sm">{msg}</p>
      <p className="text-xs text-gray-600">
        Forecasts at +1, +3, +6, +12, and +24 hours, interpolated to 15-minute steps. Sensitivity {dep.preference.sensitivity}: up to {dep.preference.max_extra_min} extra min, wait up to {dep.preference.max_wait_min} min.
      </p>
      <div className="h-48">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="wait" label={{ value: "minutes from now", position: "insideBottom", offset: -4 }} />
            <YAxis width={44} />
            <Tooltip />
            <Line type="monotone" dataKey="exposure_index" name="Exposure index" stroke="#1d4ed8" dot={false} />
            <ReferenceDot x={rec.wait_min} y={Math.round(rec.exposure_index)} r={6} fill="#16a34a" stroke="none" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

**`frontend/src/components/ChatPanel.tsx`**

```tsx
"use client";
import { useState } from "react";
import { chat, type ToolCall } from "@/lib/api";

type Msg = { role: "user" | "assistant"; text: string; calls?: ToolCall[]; cached?: boolean };

// Must match QUESTIONS in scripts/snapshot.py exactly: the saved answer is looked up by this text.
const SCRIPTED = ["I cycle from Hauz Khas to DU North Campus. Which route should I take, and when should I leave?"];

export default function ChatPanel({ sens, mode, demo, tripId, offline = false, saved = [] }: {
  sens: string; mode: string; demo: boolean; tripId: string | null; offline?: boolean;
  saved?: { question: string; answer: string; tool_calls: ToolCall[] }[];
}) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    const q = text.trim();
    if (!q || busy) return;
    if (offline) {   // no backend: answer only the saved scripted questions
      const hit = saved.find((s) => s.question.trim().toLowerCase() === q.toLowerCase());
      setText("");
      setMsgs([...msgs, { role: "user", text: q },
        { role: "assistant", text: hit ? hit.answer : "Offline demo: only the saved scripted questions can be answered.", calls: hit?.tool_calls, cached: true }]);
      return;
    }
    setText(""); setBusy(true);
    const next: Msg[] = [...msgs, { role: "user", text: q }];
    setMsgs(next);
    try {
      const r = await chat({ message: q, profile: { sensitivity: sens, mode }, demo, trip_id: tripId,
        history: next.slice(-7, -1).map((m) => ({ role: m.role, text: m.text })) });
      setMsgs([...next, { role: "assistant", text: r.answer, calls: r.tool_calls, cached: r.cached }]);
    } catch (e) {
      setMsgs([...next, { role: "assistant", text: (e as Error).message }]);
    } finally { setBusy(false); }
  }

  return (
    <div className="flex flex-col gap-2">
      {msgs.map((m, i) => (
        <div key={i} className={m.role === "user" ? "self-end rounded-lg bg-blue-50 p-2 text-sm" : "rounded-lg bg-gray-50 p-2 text-sm"}>
          <p className="whitespace-pre-wrap">{m.text}</p>
          {m.cached && <p className="mt-1 text-xs text-amber-700">Saved answer shown because the assistant was unavailable.</p>}
          {!!m.calls?.length && (
            <details className="mt-1 text-xs text-gray-600">
              <summary>Tools used: {m.calls.map((c) => c.name).join(", ")}</summary>
              {m.calls.map((c, j) => (
                <pre key={j} className="mt-1 overflow-x-auto rounded bg-white p-2">{c.name}({JSON.stringify(c.input)}){"\n→ "}{c.output}</pre>
              ))}
            </details>
          )}
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        {(saved.length ? saved.map((s) => s.question) : SCRIPTED).map((q) => (
          <button key={q} className="rounded border px-2 py-1 text-left text-xs" onClick={() => setText(q)}>{q}</button>
        ))}
      </div>
      {busy && <p className="text-sm text-gray-500">Thinking…</p>}
      <div className="flex gap-2">
        <input className="flex-1 rounded border p-2 text-sm" value={text} maxLength={500} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()} placeholder="Ask: which route and time should I choose?" />
        <button className="rounded bg-blue-600 px-3 text-sm text-white disabled:opacity-50" disabled={busy} onClick={send}>Send</button>
      </div>
    </div>
  );
}
```

**`frontend/src/app/page.tsx`** (the planner)

```tsx
"use client";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import DepartureChart from "@/components/DepartureChart";
import RouteCards from "@/components/RouteCards";
import { analyzeTrip, geocode, getConfig, type Level, type Mode, type Route, type ToolCall } from "@/lib/api";

const RouteMap = dynamic(() => import("@/components/RouteMap"), { ssr: false });

export default function Home() {
  const [from, setFrom] = useState("Hauz Khas");
  const [to, setTo] = useState("DU North Campus");
  const [mode, setMode] = useState<Mode>("cycle");
  const [sens, setSens] = useState("normal");
  const [demo, setDemo] = useState(false);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [age, setAge] = useState<number | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [dep, setDep] = useState<any>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [tripId, setTripId] = useState<string | null>(null);
  const [maxExtra, setMaxExtra] = useState(15);
  const [maxWait, setMaxWait] = useState(120);
  const [snap, setSnap] = useState<string | null>(null);
  const [levels, setLevels] = useState<Level[]>([]);
  const [offline, setOffline] = useState(false);
  const [offlineChat, setOfflineChat] = useState<{ question: string; answer: string; tool_calls: ToolCall[] }[]>([]);

  useEffect(() => { try { setSens(localStorage.getItem("sens") ?? "normal"); } catch {} }, []);
  useEffect(() => { getConfig().then((c) => setLevels(c.levels)).catch((e) => {
    if (!new URLSearchParams(window.location.search).get("offline")) setErr("Could not load the level settings: " + (e as Error).message);
  }); }, []);
  const saveSens = (v: string) => { setSens(v); try { localStorage.setItem("sens", v); } catch {} };

  async function go() {
    setBusy(true); setErr("");
    try {
      const origin = await geocode(from);          // one at a time: Nominatim allows about 1 request per second
      const destination = await geocode(to);
      const base = { origin, destination, mode, demo, sensitivity: sens, max_extra_min: maxExtra, max_wait_min: maxWait };
      const a = await analyzeTrip(base);
      setTripId(a.trip_id); setSnap(a.snapshot?.captured_at ?? null); setRoutes(a.routes.routes); setAge(a.routes.data_age_min); setDep(a.departure);
      setSel(a.routes.routes.find((r) => r.is_cleanest)?.id ?? null);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <main className="mx-auto grid max-w-6xl gap-4 p-4 lg:grid-cols-[400px_1fr]">
      <section className="space-y-3">
        <h1 className="text-xl font-semibold">AirGuard</h1>
        <input className="w-full rounded border p-2" value={from} onChange={(e) => setFrom(e.target.value)} aria-label="From" />
        <input className="w-full rounded border p-2" value={to} onChange={(e) => setTo(e.target.value)} aria-label="To" />
        <div className="flex gap-2">
          <select className="flex-1 rounded border p-2" value={mode} onChange={(e) => setMode(e.target.value as Mode)} aria-label="Mode">
            <option value="walk">Walk</option><option value="cycle">Cycle</option><option value="car">Car</option>
          </select>
          <select className="flex-1 rounded border p-2" value={sens} onChange={(e) => saveSens(e.target.value)} aria-label="Sensitivity">
            <option value="normal">Normal</option><option value="sensitive">Sensitive to air pollution</option><option value="high">Very sensitive</option>
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={demo} onChange={(e) => setDemo(e.target.checked)} /> Demo mode (frozen data)</label>
        <div className="flex gap-2 text-sm">
          <label className="flex-1">Add at most
            <select className="mt-1 w-full rounded border p-2" value={maxExtra} onChange={(e) => setMaxExtra(Number(e.target.value))}>
              {[0, 5, 10, 15, 30].map((m) => <option key={m} value={m}>{m} min</option>)}
            </select>
          </label>
          <label className="flex-1">Wait at most
            <select className="mt-1 w-full rounded border p-2" value={maxWait} onChange={(e) => setMaxWait(Number(e.target.value))}>
              {[0, 30, 60, 120, 180].map((m) => <option key={m} value={m}>{m} min</option>)}
            </select>
          </label>
        </div>
        <button className="w-full rounded bg-blue-600 p-2 text-white disabled:opacity-50" disabled={busy || offline} onClick={go}>{busy ? "Working…" : "Compare routes"}</button>
        {err && <p role="alert" className="text-sm text-red-700">{err}</p>}
        {snap && <p className="text-sm text-amber-700">Demo snapshot, captured {new Date(snap).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST. Not live data.</p>}
        {offline && <p className="text-sm text-gray-600">Offline demo: saved results only. Compare routes and live chat are switched off.</p>}
        {!snap && age !== null && <p className={`text-sm ${age > 180 ? "text-amber-700" : "text-gray-600"}`}>Air readings are about {age} minutes old (median across stations){age > 180 ? ", so estimates are less reliable" : ""}.</p>}
        {routes.length > 0 && <RouteCards routes={routes} selected={sel} onSelect={setSel} />}
        {dep && <DepartureChart dep={dep} />}
        <ChatPanel sens={sens} mode={mode} demo={demo} tripId={tripId} offline={offline} saved={offlineChat} />
      </section>
      <section className="min-h-[420px]">
        {levels.length > 0 && <RouteMap routes={routes} selected={sel} levels={levels} />}
        <p className="mt-2 text-xs text-gray-600">Segment colour is the AirGuard level of the forecast PM2.5 (µg/m³): {levels.map((l, i) => l.name.replace("_", " ") + (l.max === null ? " above " + levels[i - 1].max : " up to " + l.max)).join(", ")}. Estimates are guidance, not medical advice.</p>
      </section>
      <footer className="text-xs text-gray-500 lg:col-span-2">
        Data: OpenAQ, Open-Meteo (CAMS), NASA FIRMS. Maps © OpenStreetMap contributors. Routing by OpenRouteService. <a className="underline" href="/eval">Evaluation</a> · <a className="underline" href="/about">About and limits</a>
      </footer>
    </main>
  );
}
```

**`frontend/src/app/eval/page.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { evalMetrics, type EvalRow } from "@/lib/api";

export default function Eval() {
  const [rows, setRows] = useState<EvalRow[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => { evalMetrics().then(setRows).catch((e) => setErr((e as Error).message)); }, []);
  const data = rows.map((r) => ({ horizon: `+${r.horizon_h}h`, Model: r.mae, Persistence: r.baseline_persistence_mae, "Hour-of-day mean": r.baseline_hourly_mean_mae }));
  return (
    <main className="mx-auto max-w-3xl space-y-4 p-4">
      <h1 className="text-xl font-semibold">Forecast accuracy on a held-out window</h1>
      {err && <p role="alert" className="text-sm text-red-700">{err}</p>}
      {!err && rows.length === 0 && <p className="text-sm text-gray-600">No evaluation rows yet. Run the training script first.</p>}
      <p className="text-sm">Mean absolute error in µg/m³ (lower is better), on data the model never saw during training or tuning.</p>
      <div className="h-72">
        <ResponsiveContainer>
          <BarChart data={data}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="horizon" /><YAxis /><Tooltip /><Legend />
            <Bar dataKey="Model" fill="#1d4ed8" /><Bar dataKey="Persistence" fill="#9ca3af" /><Bar dataKey="Hour-of-day mean" fill="#d1d5db" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="w-full text-sm"><thead><tr className="text-left"><th>Horizon</th><th>MAE</th><th>RMSE</th><th>80% range covers</th><th>Avg width</th><th>Samples</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={r.horizon_h}><td>+{r.horizon_h}h</td><td>{r.mae}</td><td>{r.rmse}</td><td>{r.interval_coverage == null ? "–" : `${Math.round(r.interval_coverage * 100)}%`}</td><td>{r.interval_width ?? "–"}</td><td>{r.n_samples}</td></tr>)}</tbody></table>
    </main>
  );
}
```

**`frontend/src/app/about/page.tsx`** (levels and mode factors come from the API's `/config`, so the numbers are never repeated by hand):

```tsx
"use client";
import { useEffect, useState } from "react";
import { getConfig, type Level } from "@/lib/api";

export default function About() {
  const [levels, setLevels] = useState<Level[]>([]);
  const [factors, setFactors] = useState<Record<string, number>>({});
  const [err, setErr] = useState("");
  useEffect(() => {
    getConfig().then((c) => { setLevels(c.levels); setFactors(c.mode_factors); }).catch((e) => setErr((e as Error).message));
  }, []);
  return (
    <main className="mx-auto max-w-3xl space-y-3 p-4 text-sm">
      <h1 className="text-xl font-semibold">How AirGuard works, and what it cannot tell you</h1>
      {err && <p role="alert" className="text-red-700">{err}</p>}
      <p>AirGuard ranks route and departure options by an <b>exposure index</b>: forecast PM2.5 along each route, times travel time, times a mode factor. It is a relative index for comparing options. It is not a measured dose and it is not medical advice.</p>
      <h2 className="font-semibold">Forecasts</h2>
      <p>A model forecasts PM2.5 at stations at +1, +3, +6, +12 and +24 hours, and the app interpolates between those points. Departure steps of 15 minutes are scenario evaluations, not 15-minute forecasts. The Evaluation page shows accuracy against simple baselines and how often the forecast range covers what happened.</p>
      <h2 className="font-semibold">AirGuard levels (µg/m³)</h2>
      <p>These are AirGuard's own levels for the average forecast PM2.5 on a route. They are not official AQI categories.</p>
      <ul className="list-disc pl-5">
        {levels.map((l, i) => (
          <li key={l.name}>{l.name.replace("_", " ")}: {l.max === null ? `above ${levels[i - 1]?.max}` : `up to ${l.max}`}</li>
        ))}
      </ul>
      <h2 className="font-semibold">Mode factors</h2>
      <p>Relative breathing intake per minute, walking = 1: {Object.entries(factors).map(([m, f]) => `${m} ${f}`).join(", ")}. These are illustrative assumptions, so compare options within one mode and do not read across modes.</p>
      <h2 className="font-semibold">Sensitivity</h2>
      <p>Sensitivity never changes the exposure estimate. It changes how many extra minutes the recommendation will accept for a given reduction in exposure.</p>
      <h2 className="font-semibold">Data reliability</h2>
      <p>The reliability score combines distance to the nearest station with the width of the forecast range. It is a heuristic, not a probability that the estimate is right.</p>
      <h2 className="font-semibold">Limits</h2>
      <p>Delhi has few stations, so values between stations are interpolated. Departure planning compares leaving now with waiting; scheduled clock times are not supported.</p>
      <h2 className="font-semibold">Sources</h2>
      <p>Air quality: OpenAQ. Weather: Open-Meteo, with CAMS. Fires: NASA FIRMS. Maps: © OpenStreetMap contributors. Routing: OpenRouteService.</p>
    </main>
  );
}
```

**Host it on Amplify** (monorepo file at the repo root, `amplify.yml`):

```yaml
version: 1
applications:
  - appRoot: frontend
    frontend:
      phases:
        preBuild:
          commands: [npm ci]
        build:
          commands: [npm run build]
      artifacts:
        baseDirectory: out
        files: ["**/*"]
      cache:
        paths: [node_modules/**/*]
```

Set `NEXT_PUBLIC_API_URL` (the `ApiUrl` stack output without the trailing slash) and `NEXT_PUBLIC_MAP_STYLE_URL` as environment variables in the Amplify app, because they are baked in at build time. After the first deploy, redeploy the backend with `AllowedOrigins` set to your Amplify URL. Vercel's free tier is the backup host for the same static build.

**Frontend checklist:** a loading state, an empty state, an error message that comes from the API's `error.message`, a banner when data is stale, a visible disclaimer, attribution in the footer, text labels next to every colour, and a layout that works at phone width.

## Appendix I: Demo trip, frozen snapshot, and caching

Live air data changes every hour, so a demo that depends on it can show different numbers each run or fail on stage. The fix is to freeze a snapshot of the forecasts, precompute the demo routes and agent answers against it, and quote only numbers your own script prints.

**Pick the demo trip with these tests**

- The routing service returns at least 2 alternatives that follow visibly different roads.
- At least 3 stations lie within a few kilometres of the route, so the numbers rest on more than one sensor.
- Exposure differs noticeably between alternatives, and the cleaner one costs only a few extra minutes.
- The duration is realistic for the mode (a 15 to 40 minute ride, a 20 to 50 minute walk).

Candidate trips (coordinates are approximate; check each on a map before using it):

| Trip | Mode | Origin | Destination |
| --- | --- | --- | --- |
| Hauz Khas to DU North Campus | cycle | 28.5494, 77.2001 | 28.6889, 77.2100 |
| Lodhi Garden to Connaught Place | walk | 28.5931, 77.2197 | 28.6315, 77.2167 |
| India Gate to Nehru Place | car | 28.6129, 77.2295 | 28.5491, 77.2519 |

**Persona for the pitch:** a named student who cycles to college at 8 AM, with the app's sensitivity setting on. Keep it to one person and one trip.

**`scripts/snapshot.py`** (run on the morning of the demo, after the hourly job has refreshed the forecasts):

```python
import hashlib
import json
import random
import statistics
from datetime import datetime, timezone

from agent.agent import chat
from api import service
from common import db
from engine.exposure import level_config

TRIPS = [{"name": "Hauz Khas to DU North Campus", "mode": "cycle", "o": "hauz khas", "d": "du north campus"}]
QUESTIONS = [
    "I cycle from Hauz Khas to DU North Campus. Which route should I take, and when should I leave?",
]


def pt(place):
    lat, lon = service.geocode(place)
    return {"lat": lat, "lon": lon}


def freeze_stations():
    stations, age = service.load_stations()
    snap = [{"id": s.id, "lat": s.lat, "lon": s.lon, "series": [list(p) for p in s.series]} for s in stations]
    db.upsert("route_cache", [{"key": "snapshot:stations", "response": {"captured_at": datetime.now(timezone.utc).isoformat(),
                                                       "data_age_at_capture_min": age, "stations": snap}}], "key")
    print(f"froze {len(snap)} stations; data was {age} minutes old")


def headline(t):
    o, d = pt(t["o"]), pt(t["d"])
    res = service.score_trip(o, d, t["mode"], 0.0, demo=True)
    fast = next(r for r in res["routes"] if r["is_fastest"])
    clean = next(r for r in res["routes"] if r["is_cleanest"])
    dep = service.departure(o, d, t["mode"], 0.0, 4.0, 120, demo=True, sensitivity="sensitive")
    return {"trip": t["name"], "routes": len(res["routes"]),
            "cleanest_vs_fastest": {"extra_min": round(clean["duration_min"] - fast["duration_min"], 1),
                                    "exposure_reduction_pct": round(100 * (fast["exposure_index"] - clean["exposure_index"]) / fast["exposure_index"], 1)
                                    if fast["exposure_index"] else 0.0},
            "departure": dep["delta"], "recommended_wait_min": dep["recommended"]["wait_min"],
            "reliability": clean["confidence"]}


def offline_files(t, saved):
    o, d = pt(t["o"]), pt(t["d"])
    body = {"trip": t["name"], "snapshot": service.snapshot_info(), "levels": level_config(), "chat": saved, "routes": service.score_trip(o, d, t["mode"], 0.0, demo=True),
            "departure": service.departure(o, d, t["mode"], 0.0, 4.0, 120, demo=True, sensitivity="sensitive")}
    json.dump(body, open("frontend/public/demo/trip1.json", "w"))


def cache_answers():
    saved = []
    for q in QUESTIONS:
        out = chat(q, {"sensitivity": "sensitive", "mode": "cycle"}, [], demo=True)
        key = "agent:" + hashlib.sha1(q.strip().lower().encode()).hexdigest()   # same formula as agent/handler.py
        db.upsert("route_cache", [{"key": key, "response": out}], "key")
        print("cached answer for:", q)
        saved.append({"question": q, **out})
    return saved


def batch_stats(mode="cycle", n=30, seed=1):
    """Median trade-off over random trips, so you can make a claim wider than one route."""
    random.seed(seed)
    stations, _ = service.load_stations(demo=True)
    out = []
    for _ in range(n):
        a, b = random.sample(stations, 2)
        res = service.score_trip({"lat": a.lat, "lon": a.lon}, {"lat": b.lat, "lon": b.lon}, mode, 0.0, demo=True)
        fast = next(r for r in res["routes"] if r["is_fastest"])
        clean = next(r for r in res["routes"] if r["is_cleanest"])
        out.append((clean["duration_min"] - fast["duration_min"], 100 * (fast["exposure_index"] - clean["exposure_index"]) / (fast["exposure_index"] or 1)))
    return {"n": n, "median_extra_min": round(statistics.median(x for x, _ in out), 1),
            "median_reduction_pct": round(statistics.median(y for _, y in out), 1)}


if __name__ == "__main__":
    freeze_stations()
    summary = {"trips": [headline(t) for t in TRIPS], "batch": batch_stats()}
    json.dump(summary, open("docs/headline.json", "w"), indent=2)
    print(json.dumps(summary, indent=2))
    saved = cache_answers()
    for t in TRIPS:
        offline_files(t, saved)
```

Create the folder first with `mkdir -p frontend/public/demo docs`. The script walks station pairs for the batch figure, so the batch result describes trips between station locations in your data, not every trip in Delhi; say so if you quote it.

**Snapshot timing.** The snapshot keeps its forecast offsets relative to the moment it was captured, so capture it at the time of day you will present (for example early morning for an 8 AM commute story). The script stores the capture time, and the interface shows "Demo snapshot, captured \[time\] IST. Not live data." instead of a data age. Replaying the snapshot later does not change which forecast points the optimizer uses, because the offsets are relative to the capture, but any clock time you say aloud will differ from the capture time, so describe it as "a snapshot captured at \[time\]".

**Add a scripted-question button** to the chat panel so the presenter never types: a button that fills the input with the exact text from `QUESTIONS`. The cached answer is looked up by that exact text (lower-cased and trimmed).

**Add an offline switch to the planner** so the UI renders even if the backend is down, and loads the demo trip as soon as the page opens. Add this effect with the other effects in the component instead of editing `go()` in `page.tsx`:

```tsx
useEffect(() => {
  if (!new URLSearchParams(window.location.search).get("offline")) return;
  fetch("/demo/trip1.json").then((r) => r.json()).then((j) => {
  setOffline(true); setLevels(j.levels); setOfflineChat(j.chat ?? []);
    setRoutes(j.routes.routes); setAge(null); setSnap(j.snapshot?.captured_at ?? null); setDep(j.departure);
  setSel(j.routes.routes.find((r: Route) => r.is_cleanest)?.id ?? null);
  }).catch(() => setErr("The offline demo file is missing."));
}, []);
```

In offline mode the page also reads the level configuration and the saved scripted answers (with their tool traces) from the same file, so the map, its legend, and the scripted question all work without the backend. Compare routes is switched off, and the chat answers only the saved questions; that is the limit of the offline fallback, so don't promise more than that.

**Rules for the headline number**

- Quote only what `docs/headline.json` prints, for example "in our frozen snapshot of \[date and time\], Route 2 added X minutes and AirGuard estimated a Y% lower exposure index".
- One trip is an example, not a result. If you want a general claim, use the batch figure and state how many trips it covers.
- Always add the reliability value and say that the data comes from a sparse sensor network.

**Fallback ladder for the live demo**

| If this fails | Do this |
| --- | --- |
| The model call (Bedrock) | The handler returns a saved answer only for the exact scripted questions you preloaded (only when Demo mode is on, for the demo trip and the sensitive-cyclist profile); any other question gets a plain error message, and saved answers are labelled as saved |
| The routing service | Routes come from `route_cache`; demo trips are already stored there |
| Fresh air data | Tick "Demo mode" to use the frozen snapshot |
| The whole backend or the paused database | Open the page with `?offline=1`, or play the recorded video |
| Everything at once | Show the screenshots and the video, and talk through the architecture diagram |

**Day-of protocol**

1. Morning: invoke the ingestion Lambda by hand, check `/health`, open the Supabase dashboard to confirm the project is active, then run `python scripts/snapshot.py`.
2. Rehearse the full script three times in demo mode, timing it to 2 to 3 minutes.
3. Record the video in demo mode and keep an unedited backup take.
4. Use live mode only as an optional extra, after `/health` reports fresh data.
5. Take screenshots of the map, the departure chart, the tool-call panel, and the evaluation page.

## Appendix J: Judging criteria map and submission template

The hackathon's judging criteria and prize list were not in the pages you shared, so the first column below is a placeholder to replace with the exact wording from the hackathon page. Do this on Day 1; it decides what the demo emphasises.

**To fill in from the hackathon page:** the list of criteria and any weights, the prize categories (track prizes, special prizes for AWS tool usage, and so on), the submission format (video length, repo link, write-up fields), the deadline in IST, and any rule about regions, team size, or open-source licensing. Also confirm the eligibility wording itself: the page you shared says a project must use at least one AWS open source tool or be deployed on AWS, and lists Strands Agents SDK as an open source tool, but check that text on the official page and whether a local-only project is accepted.

| Criterion (replace with the exact wording) | Where AirGuard answers it | Evidence to show |
| --- | --- | --- |
| Impact and problem fit | A named commuter, a Delhi trip, a lower-exposure route and departure time | The headline numbers from `docs/headline.json`, plus the batch median |
| Technical execution | Forecast model, exposure engine, deployed stack, tests | The evaluation page, passing tests, a working public URL |
| Use of AWS | Strands Agents SDK (open source), Lambda, API Gateway, EventBridge, S3, SSM, Bedrock if covered by credits | The architecture diagram, the stack template, the visible tool-call trace |
| Innovation | Departure-time optimisation and a tool-using agent rather than a static AQI map | The departure chart and the agent's explanation |
| Responsible AI | Numbers come from tools, uncertainty shown, no medical advice | The reliability score, the stated assumptions, the disclaimer |
| Presentation and demo | A rehearsed 2 to 3 minute script on frozen data | The video, the backup take, the screenshots |
| Documentation | README with setup and architecture | The repo README and this guide's structure |

**Submission write-up template** (fill the brackets with measured values):

```text
Problem
On bad-air days Delhi commuters see AQI numbers but nothing tells them what to do differently.

Solution
AirGuard compares alternative routes and departure times by estimated PM2.5 exposure, using a forecast
that is evaluated on held-out data, and explains the trade-off through an AI agent that only reports
numbers returned by its tools.

Result
On [trip] in a frozen snapshot of [date, time], the lowest-exposure route added [X] minutes and AirGuard
estimated a [Y]% lower exposure index (a model estimate, not a measured dose). Leaving [Z] minutes later cut it by [W]% for a total of [V] extra minutes.
Across [N] trips between station locations the median trade-off was [A] minutes for [B]%.

How it works
1. Hourly job: air quality, weather and fire data -> features -> XGBoost forecast per horizon -> database.
2. Exposure engine: route segments x interpolated forecast x travel time x mode factor.
3. Strands agent: calls the same functions as tools and explains the result.

AWS
Strands Agents SDK (open source); Lambda and API Gateway (API and agent); EventBridge (hourly job);
S3 (model files); SSM (secrets); [Bedrock model, if used].

Evidence
Forecast error on a held-out [14]-day window: [table or link]. Live pipeline check over [N] days: [MAE per horizon]. Unit tests for the exposure math.

Honest limits
A sparse sensor network; exposure is an index based on stated assumptions; forecast horizon 24 hours.

Next
School-run mode, more cities, a public API. Production would replace Open-Meteo's free non-commercial tier with a licensed or self-hosted weather source.
```

## Appendix K: Day 1 verification checklist and decision rules

Each check below can change the design, so do them in the first hours, in this order. Thresholds in the decision rules are my judgement, not facts about your data; adjust them if the results suggest otherwise.

In local-first mode, checks 3 (Bedrock), 6 (hello-world deploy), and 8 (Budgets alert) only matter if you decide to deploy; do them then.

- [ ] **1. OpenAQ key and station coverage**

```bash
curl -s -H "X-API-Key: $OPENAQ_API_KEY" \
  "https://api.openaq.org/v3/locations?bbox=76.80,28.35,77.55,28.95&parameters_id=2&limit=1000" \
  | python -c "import sys, json; print(len(json.load(sys.stdin)['results']), 'PM2.5 locations')"
```

Then run `openaq.pm25_stations()` and count the `active` ones. Decision: about 12 or more active stations, proceed as planned. Between 6 and 11, proceed but narrow the claim to the areas the stations cover and say so. Fewer than 6, lower the claims and make the sparse-data story the first slide. Adding Open-Meteo's coarse air-quality values (about 45 km and 3-hourly over India) as a covariate would be an extension you build yourself; this guide has no code for it.

- [ ] **2. History depth.** Run `select station_id, count(*), min(ts), max(ts) from measurements group by 1;` after the backfill. Decision: 90 or more days for most stations is enough to train. Less than that, train only the +1, +3 and +6 hour horizons (the command is under "Thin history" in Appendix D) and say so. The training script prints how many stations and rows each split has and skips any horizon with too little data.
- [ ] **3. Bedrock access and credit coverage**

```bash
aws bedrock-runtime converse --region us-east-1 --model-id amazon.nova-2-lite-v1:0 \
  --messages '[{"role":"user","content":[{"text":"Say hello"}]}]'
```

Then open Billing, then Credits, and look at the applicable products. AWS staff answers on re:Post say promotional credits apply to AWS services but not to AWS Marketplace purchases, and that third-party models such as Claude are sold through the Marketplace while Amazon's own models are AWS services; those answers are a couple of years old, so confirm on your account. Nova 2 Lite's model card lists the model ID, geo inference IDs, and a global inference ID; the availability table I saw lists Mumbai only for the `global.` inference profile. Decision: if access is denied, enable the model in the Bedrock console; if it still fails, try `amazon.nova-lite-v1:0`; if neither works, use Ollama in development, serve cached answers on the deployed site, and say so in the submission. Strands still qualifies you either way.

- [ ] **4. Routing alternatives for your demo trip**

```bash
curl -s -X POST "https://api.openrouteservice.org/v2/directions/cycling-regular/geojson" \
  -H "Authorization: $ORS_API_KEY" -H "Content-Type: application/json" \
  -d '{"coordinates":[[77.2001,28.5494],[77.2100,28.6889]],"alternative_routes":{"target_count":3,"share_factor":0.6,"weight_factor":1.6}}' \
  | python -c "import sys, json; print(len(json.load(sys.stdin)['features']), 'routes')"
```

Decision: one route only means loosening the factors (forum examples use `share_factor` 0.8 and `weight_factor` 2) or choosing a different trip. If no demo trip returns two routes, build alternatives by routing through an offset midpoint waypoint.

- [ ] **5. Fire data key.** `curl -s "https://firms.modaps.eosdis.nasa.gov/api/area/csv/$FIRMS_MAP_KEY/VIIRS_SNPP_NRT/73.5,28.0,78.0,32.5/2" | head -3` should print a header row. Decision: an error mentioning the key means requesting a new one; an empty result outside the burning season is normal, and the feature then stays near zero.
- [ ] **6. Hello-world deploy.** Deploy the smallest stack (the API function and `/health`) and call it from your laptop. Decision: if image builds fail, fix Docker first; as a stopgap deploy the API as a zip (it needs no ML libraries) and add the other two functions as images later.
- [ ] **7. Supabase from Lambda.** Confirm the project is active and that a Lambda can read `stations`. Open the dashboard once a day so the free project doesn't pause.
- [ ] **8. AWS Budgets alert** exists at $1, and the billing page shows credits and no charges.
- [ ] **9. Judging criteria** pasted into Appendix J, with the deadline converted to IST.
- [ ] **10. Pick the demo trip** using Appendix I's tests, and record its coordinates.

**Things I could not verify, and how to resolve each**

| Open item | How to resolve |
| --- | --- |
| Exact `BedrockModel` constructor options in your Strands version | Read the current Strands docs page for the Bedrock provider, or run `help(BedrockModel)` |
| Field names in OpenAQ `/hours` and `/locations` responses | Print one raw result and adjust the key names in `ingestion/openaq.py` |
| Open-Meteo request limits for non-commercial use | Read their terms page, cache responses, and keep calls to a few per hour |
| FIRMS maximum day range per request | Check the API page; reduce the 5-day window if you get an error |
| CPCB PM2.5 category cutoffs | No longer used for route levels. For official AQI categories, compute them from 24-hour averages using CPCB's table; otherwise choose and justify your own cutoffs and edit `RISK_BANDS` |
| Mode factors | Choose values from a source you cite, and update the about page |
| OpenRouteService daily quota | Look at your dashboard; cache routes in `route_cache` |
| Amplify free-tier limits | Check the Amplify pricing page; Vercel is the backup |
| Whether credits cover Nova and your other AWS usage | Billing, then Credits, then applicable products |
| Hackathon rules on regions, licenses, and submission items | The hackathon page and its organisers |

## Appendix L: Day-by-day checklist for all 3 days

This is the working checklist: tick items as you go. Person A owns data, ML, and the engine; Person B owns the API, agent, frontend, AWS, and demo. Each task names its appendix. Every day ends with a gate: all gate items must be ticked before the next day starts. If one fails, apply that day's cut rule instead of pushing through.

**Local-first mode:** the plan is to run locally first and deploy only if needed. Until the Day 2 gate, read every deploy, AWS, Bedrock, and public-URL task below as optional, and use the local equivalent from Appendix M (for example, run the same check against `localhost` instead of the deployed URL).

**Team routine:** a 15-minute sync at the start, middle, and end of each day (done, blocked, next); merge to `main` at least twice a day; keep `main` deployable; write decisions in a `docs/decisions.md` file as you make them.

### Day 1: foundations and a deployed vertical slice

**Hours 0 to 3, both of you**

- [ ] Read the hackathon page; paste the judging criteria, prizes, deadline (in IST), and submission format into Appendix J.
- [ ] Create accounts and keys: AWS free plan with a $1 Budgets alert, Supabase (US East), OpenAQ, FIRMS, OpenRouteService, GitHub, Ollama (Appendix A).
- [ ] Create the repo, virtual environment, and folders (Appendix B).
- [ ] Agree the API contract: write the Pydantic models, export `contracts/openapi.json` (Appendix B step 8, Appendix F).
- [ ] Run Appendix K checks 1 to 5 (stations, Bedrock, routing alternatives, fire key) and write the decisions down.

**Person A, hours 3 to 12**

- [ ] Create the tables: main schema, Appendix C changes, Appendix D `forecasts_latest` and row-level security.
- [ ] Add `common/` helpers and the three ingestion modules (Appendix C); run `scripts/backfill.py`; do its four sanity checks.
- [ ] Write `engine/exposure.py` and the tests; `pytest -q` is green (Appendix E).
- [ ] Unblock Person B: write a temporary persistence forecast into `forecasts_latest` (rows for horizons 0, 1, 3, 6, 12, and 24, each equal to the latest observed value, with low and high at about 30% either side). It is replaced by the real model on Day 2.

**Person B, hours 3 to 12**

- [ ] Get `api/service.py` and `api/main.py` running locally (`uvicorn`), with `/docs` open (Appendix F).
- [ ] Deploy a hello-world stack: Docker builds, `sam deploy`, `curl ${API}health` works (Appendix F, Appendix K check 6).
- [ ] Scaffold the Next.js app with the map and planner calling the local API (Appendix H).
- [ ] Get the Strands agent answering with `now_ist`, `geocode`, and `score_routes` on Ollama (Appendix G).

**Day 1 gate (end of day, both)**

- [ ] One candidate demo trip returns at least 2 routes with exposure scores, locally and from the deployed `/routes/score`.
- [ ] Deployed `/health` reports a station count above zero.
- [ ] `pytest -q` passes and everything is on `main`; both of you can run `sam build && sam deploy`.
- [ ] Appendix K items 1 to 8 are resolved and the decisions are written down.

**Cut rule if behind:** keep the temporary persistence forecast longer, skip the fire features, and postpone the chat panel. Do not skip the deploy.

### Day 2: the core product

**Morning, Person A**

- [ ] Train the model with `python -m ml.train`; read the metrics table; upload the models to S3 (Appendix D).
- [ ] Hand-check the exposure math in a spreadsheet and keep the sheet (Appendix E).
- [ ] Deploy the ingestion Lambda, invoke it once by hand, and confirm `forecasts_latest` now holds model rows for horizons 0 to 24 (Appendix D, Appendix F).

**Morning, Person B**

- [ ] Wire all agent tools (`geocode`, `get_forecast`, `score_routes`, `best_departure_time`); test on Ollama, then on Bedrock; confirm `tool_calls` appears in the response (Appendix G).
- [ ] Build the route cards, coloured map, departure chart, and chat panel with the tool trace (Appendix H).

**Afternoon, Person A**

- [ ] Test the edge cases: a route over 100 km, a stale station, a point outside Delhi, a departure 20 hours away; each should return a clear message, not a crash (Appendix E, Appendix F).
- [ ] Confirm `/eval` returns one row per horizon you trained, and the numbers look sane against the baselines.
- [ ] Check reliability behaves: it should fall for points far from any station.

**Afternoon, Person B**

- [ ] Deploy the agent function and confirm the throttle works; handle the 30-second limit (Appendix F troubleshooting).
- [ ] Deploy the frontend on Amplify with the two environment variables, then redeploy the backend with `AllowedOrigins` set to the Amplify URL (Appendix H).
- [ ] Build the evaluation and about pages: assumptions, risk bands, attributions, disclaimer.

**Day 2 verification commands**

```bash
API=$(aws cloudformation describe-stacks --stack-name airguard \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
curl -s ${API}health
curl -s -X POST ${API}routes/score -H 'content-type: application/json' \
  -d '{"origin":{"lat":28.5494,"lon":77.2001},"destination":{"lat":28.6889,"lon":77.2100},"mode":"cycle"}' | python -m json.tool | head -30
curl -s -X POST ${API}agent/chat -H 'content-type: application/json' \
  -d '{"message":"I cycle from Hauz Khas to DU North Campus. Which route and when?","profile":{"sensitivity":"sensitive","mode":"cycle"}}'
sam logs -n IngestFunction --stack-name airguard --start-time "3hours ago"
```

**Day 2 gate (end of day, both)**

- [ ] From the public frontend URL, on a laptop and a phone: enter a trip, see routes, departure advice, and an agent answer with a visible tool trace.
- [ ] The evaluation page shows real numbers with both baselines.
- [ ] The hourly job has run at least 3 times in a row without errors (check the logs).
- [ ] Tests pass; no secrets are committed (`git grep -nE "(SERVICE_KEY|API_KEY)=.+" -- . ':!*.example'` prints nothing); the billing page shows no charges.

**Cut rule if behind:** drop the email tool, the batch statistics, and the about-page polish; keep the demo path (planner, departure advice, agent, evaluation page) working end to end.

### Day 3: freeze, polish, and submit

**Before midday, both**

- [ ] Bug bash: invalid coordinates, a place outside Delhi, `mode` set to `bus`, a departure 20 hours away, a stale station, a wrong routing key, a wrong Bedrock model ID. Each should show a clear message or a fallback.
- [ ] Run a separate AI agent against the chat endpoint with 20 adversarial prompts (asking for medical advice, for made-up numbers, for other cities) and confirm no invented numbers appear.
- [ ] Open the Supabase dashboard, invoke the ingestion Lambda, then run `python scripts/snapshot.py`; pick the final demo trip and check `docs/headline.json` (Appendix I).
- [ ] Break Bedrock on purpose and confirm the saved-answer label appears; open the page with `?offline=1` and confirm it renders.
- [ ] Check phone layout, text labels next to colours, the footer attributions, and the disclaimer.

**Midday: feature freeze**

- [ ] Tag the commit (`git tag v1-freeze`). After this, only labelled bug fixes; no new features.

**Afternoon, both**

- [ ] Write the README: problem, architecture diagram, setup steps, screenshots, assumptions, limits, how to run the tests.
- [ ] Record the 2 to 3 minute demo video in demo mode, plus an unedited backup take; play it back to check audio and legibility.
- [ ] Take the screenshots: map, departure chart, tool-call panel, evaluation page.
- [ ] Fill the submission text from the Appendix J template using numbers printed by your scripts and the evaluation table.
- [ ] Walk the Appendix J table: every criterion has evidence you can point to.
- [ ] Final deploy from the freeze tag; smoke-test `/health`, the planner, the agent, and the evaluation page from a fresh browser and a phone.
- [ ] Submit at least 3 hours before the deadline and confirm the submission was received.

**After judging**

- [ ] Run `sam delete --stack-name airguard`, delete the models bucket, the container registry repositories, and the SSM parameters; confirm the billing page shows no charges.

**Cut rule if behind (Day 3):** protect, in order, the deployed URL, the demo video, the README, and the submission text. Drop polish before any of those.

**Checkpoints that tell you early if you are slipping**

| Checkpoint | If you are behind |
| --- | --- |
| End of hour 3, Day 1: accounts, repo, and Appendix K checks 1 to 5 done | Ask the other person to take over the accounts; the checks decide the design, so do them before coding |
| Middle of Day 1: backfill finished, engine tests green | Reduce to the 10 best stations and 90 days of history |
| End of Day 1: deployed vertical slice | Stop adding features; fix the deploy first |
| Middle of Day 2: trained model and a metrics table | Train only the +1, +3, and +6 hour horizons |
| End of Day 2: public URL works end to end | Cut optional features; the demo path comes first |
| Midday Day 3: freeze | Freeze anyway; ship what works and document the limits |

## Appendix M: Local-first mode (run on your laptop, deploy only if needed)

In this mode everything runs on your laptop except the free hosted Supabase database and the free data APIs. Strands Agents SDK is listed as an AWS open source tool on the hackathon page you shared, so a local build should meet the eligibility rule; confirm that on the official page. What you give up is a public URL that judges can click, so you show the demo from your laptop and in the video, and your README must let a stranger run the project.

**Local equivalents of the planned steps**

| Planned step | Local-first equivalent |
| --- | --- |
| Deploy hello-world and call `/health` | `uvicorn api.main:app --port 8000`, then `curl localhost:8000/health` |
| Ingestion Lambda every hour | Leave `scripts/run_hourly.py` running in a terminal (patch 3), or run it by hand each morning |
| Model files in S3 | Keep them in `models/v1` and set `MODEL_DIR=models/v1` (patch 1) |
| Agent Lambda behind API Gateway | A `/agent/chat` route in the local API (patch 2) |
| Bedrock model | Ollama: `LLM_BACKEND=ollama` in `.env` |
| Amplify frontend | `cd frontend && npm run dev` with `NEXT_PUBLIC_API_URL=http://localhost:8000` |
| CORS for the Amplify URL | `ALLOWED_ORIGINS=http://localhost:3000` |
| Public URL smoke test | The same checks against `localhost`; for your phone see below |
| Budgets alert, SSM, container registry, `sam delete` | Not needed until you deploy |
| Final deploy from the freeze tag | Run the frozen build locally and record the video from it |

Add these to your local `.env`: `LOCAL=1`, `MODEL_DIR=models/v1`, `LLM_BACKEND=ollama`.

**Run order**

```bash
# terminal 1 (skip if the Ollama app is already running)
ollama serve
# terminal 2: API
uvicorn api.main:app --reload --port 8000
# terminal 3: frontend
cd frontend && npm run dev
# terminal 4: keeps forecasts fresh
PYTHONPATH=. python scripts/run_hourly.py

# smoke tests
curl -s localhost:8000/health
curl -s -X POST localhost:8000/routes/score -H 'content-type: application/json' \
  -d '{"origin":{"lat":28.5494,"lon":77.2001},"destination":{"lat":28.6889,"lon":77.2100},"mode":"cycle"}' | python -m json.tool | head -30
```

**Testing on your phone** (same Wi-Fi as the laptop): start the API with `--host 0.0.0.0`, start the frontend with `npm run dev -- -H 0.0.0.0`, set `NEXT_PUBLIC_API_URL=http://<laptop-ip>:8000`, and add `http://<laptop-ip>:3000` to `ALLOWED_ORIGINS`.

**Patch 1: `ingestion/handler.py`.** Replace `load_models` so it can read local files and needs no AWS credentials:

```python
def load_models():
    if _M:
        return _M
    version = os.environ.get("MODEL_VERSION", "v1")
    d = os.environ.get("MODEL_DIR")           # local runs: MODEL_DIR=models/v1
    if not d:
        s3, d = boto3.client("s3"), tempfile.mkdtemp()
        s3.download_file(cfg()["MODEL_BUCKET"], f"models/{version}/meta.json", f"{d}/meta.json")
        for h in json.load(open(f"{d}/meta.json"))["horizons"]:
            s3.download_file(cfg()["MODEL_BUCKET"], f"models/{version}/h{h}.json", f"{d}/h{h}.json")
    meta = json.load(open(f"{d}/meta.json"))
    models = {}
    for h in meta["horizons"]:
        m = xgb.XGBRegressor()
        m.load_model(f"{d}/h{h}.json")
        models[h] = m
    _M.update(meta=meta, models=models, version=version)
    return _M
```

**Patch 2: `api/main.py`.** Add a chat route for local use. When deployed, API Gateway sends `POST /agent/chat` to the agent function instead, so this route is only used locally:

```python
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    profile: dict | None = None
    trip_id: str | None = None
    history: list[dict] = []
    demo: bool = False


@app.post("/agent/chat")
def agent_chat(req: ChatRequest):
    from agent.agent import chat                      # imported here so the API image never loads the agent libraries
    from agent.handler import _cached, _history
    try:
        return chat(req.message, req.profile, _history(req.history[-6:]), req.demo, req.trip_id)
    except Exception as e:
        print("agent failed:", repr(e))
        hit = _cached(req.message) if req.demo else None
        if hit:
            return {**hit, "cached": True}
        raise HTTPException(503, "The assistant is unavailable right now. The route and departure results still work.")
```

**Patch 3: `scripts/run_hourly.py`**

```python
import time
import traceback

from ingestion.handler import lambda_handler

while True:
    try:
        print(lambda_handler({}, None))
    except Exception:
        traceback.print_exc()
    time.sleep(3600)
```

**How the checklists change in local-first mode**

- Day 1 and Day 2 gates: run each check against `localhost` (and your phone on the same network) instead of a deployed URL.
- Day 3: record the video and take the screenshots from the local run in demo mode; skip the final deploy and cleanup.
- Submission: say plainly that the project runs locally and link the repo and video; put a "Run it in 5 minutes" section at the top of the README (clone, copy `.env.example`, add keys, three commands).
- A judge may not have your API keys. Keep `frontend/public/demo/trip1.json` (Appendix I) so the interface can still render the demo trip with `?offline=1`.

**When to deploy, and in what order.** Deploy only if, at the Day 2 gate, the local demo works end to end, the tests pass, and several hours remain. Do it in small independent steps, stopping whenever time runs short:

1. The frontend only, as a static site in offline-demo mode (free on Amplify or Vercel). It gives judges a clickable URL with no backend to break.
2. The API Lambda, then point the frontend at it.
3. The agent Lambda (Appendix K check 3 first).
4. The hourly ingestion Lambda.

Each step is covered in Appendix F and Appendix H. Anything you don't deploy keeps running locally.
