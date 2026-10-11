<div align="center">

# AirGuard

**Same commute. Less smoke.**

AirGuard reads the PM2.5 forecast along every route you could take in the next few hours,
then tells Delhi commuters which way to go and when to leave so they breathe less of it.

[🚀 Quick Start](#quick-start) · [📚 Docs Guide](#documentation-guide-start-here) · [🏗️ Architecture](docs/architecture.md) · [🔬 Methodology](docs/methodology.md) · [📊 Evidence](#evidence) · [🤝 Contributing](CONTRIBUTING.md)

</div>

---

## 📚 Documentation Guide (Start Here)

If you are new to the repository, here is the fastest way to find what you need:

| Guide | What it covers | Who it is for |
| :--- | :--- | :--- |
| **[Local Setup Guide](docs/setup.md)** | Step-by-step environment setup (Python 3.12, Node 20+, Supabase, Ollama), API keys, phone testing, and troubleshooting | Developers getting the project running locally |
| **[Architecture & Data Flow](docs/architecture.md)** | System components, Mermaid flowcharts, hourly ingestion pipeline, request path for trip analysis, and code map | Engineers exploring how the frontend, API, ML, and agent connect |
| **[Methodology & Assumptions](docs/methodology.md)** | Mathematical formulation: exposure dose index ($\sum C_i \times t_i \times m$), 200 m IDW spatial field, conformal interval calibration, and utility decision rules | Data scientists and researchers examining modeling rigor |
| **[Database & Migrations](docs/database.md)** | PostgreSQL / Supabase schema, table definitions, migration workflow, RLS security model, and `setup.sql` | Developers working with data persistence or hosted Supabase |
| **[Design Decision Log](docs/decisions.md)** | 14 Architectural Decision Records (ADRs) explaining technical trade-offs (e.g. psycopg vs REST API, CPCB feed delay handling, small model steering) | Anyone wanting the context and rationale behind choices |
| **[Contributing Guidelines](CONTRIBUTING.md)** | Code style, git workflow, testing requirements, and quality checks | Contributors wanting to submit pull requests |

---

## The problem

On bad-air days, Delhi's AQI apps show a map of numbers. They don't change what anyone does. Yet the
same trip can mean very different exposure depending on the road you take and the hour you leave:
PM2.5 swings through the day as the boundary layer rises and falls, and it varies street to street.

AirGuard is for the people who feel that difference most: people who cycle or walk to college or work,
riders on two-wheelers, people with asthma, and parents on the school run.

## What it does

- **Compares real routes** for walking, cycling, two-wheelers or a car, each coloured every 200 m by
  forecast PM2.5 along the way.
- **Finds a better time to leave**, checking every 15 minutes over the next few hours (up to 6 hours ahead).
- **Fits your limits.** You say how sensitive you are and how much extra time you'll accept; it never
  suggests more. Sensitivity changes the trade-off, never the pollution numbers.
- **Explains itself.** An assistant built on the **Strands Agents SDK** answers follow-up questions using
  only numbers its tools return. Every tool call is visible, and every number is verified before you see it.
- **Says how sure it is.** Every exposure figure carries a forecast range and a confidence score; stations
  whose feeds are delayed are marked as estimates.

## How it works

```mermaid
flowchart LR
  A["OpenAQ stations<br/>Open-Meteo weather + CAMS<br/>NASA FIRMS fires"] --> B["Hourly job<br/>XGBoost forecast per station<br/>now … +24 h"]
  B --> C[("Postgres<br/>(Supabase)")]
  C --> D["Exposure engine<br/>routes × 200 m × forecast × time"]
  E["OSRM routes"] --> D
  D --> F["Decision rule<br/>your sensitivity + limits"]
  F --> G["Strands agent<br/>traced tools + number guard"]
  F & G --> H["Web app<br/>map · chart · assistant"]
```

1. **Forecast.** Each hour, one XGBoost model per horizon forecasts PM2.5 at ~76 stations from their recent
   readings, neighbouring stations, the CAMS global model, weather (incl. boundary-layer height) and crop
   fires detected upwind.
2. **Score.** Each candidate route is cut into 200 m segments; each segment gets the forecast for the minute
   you'd reach it, blended from the nearest stations via Inverse-Distance Weighting (IDW).
3. **Decide.** Every route × every 15-minute departure is scored; the recommendation is the lowest-exposure
   option whose exposure saving is worth its extra time to you under your profile limits.
4. **Explain.** The assistant reads the saved analysis through tools and explains the trade-off with guaranteed
   number grounding.

Details and every assumption: [docs/methodology.md](docs/methodology.md).

## Evidence

The forecast is tested on the most recent two weeks (27 Sep – 11 Oct 2026), which it never saw in
training, at 76 stations. Mean absolute error in µg/m³, lower is better:

| Horizon | AirGuard | Last reading | Station's usual for that hour | CAMS global model |
| --- | ---: | ---: | ---: | ---: |
| +1 h | **7.6** | 8.0 | 42.6 | 29.6 |
| +3 h | **12.6** | 15.8 | 42.3 | 29.6 |
| +6 h | **14.5** | 21.0 | 42.2 | 29.7 |
| +12 h | **16.5** | 26.1 | 41.2 | 29.9 |
| +24 h | **17.3** | 18.3 | 40.0 | 30.2 |

*Baselines: **Last reading** assumes conditions persist unchanged; **Station's usual** is the historical average for that hour of day; **CAMS** is the raw European Copernicus global model (~45 km resolution).*

During a network-wide CPCB feed outage (every CPCB station hidden, only independent sensors left), the
model still estimates each station within **16.5–20.9 µg/m³** MAE, against 29.7–30.8 for raw CAMS. The
80% forecast ranges contained the true value 71–85% of the time across the first 12 hours. Model
`v20261011-0550`; full results on the app's **Evidence** page. These measure the station forecast; values
along a route are interpolated and carry their own confidence.

## Quick start

You need Python 3.12, Node 20+, Docker or Podman, and optionally Ollama. One free key:
[OpenAQ](https://explore.openaq.org/register).

```bash
make setup                       # Python venv, npm install, pulls the local LLM (qwen3:1.7b)
echo "OPENAQ_API_KEY=..." >> .env.local
make db-start                    # local Supabase + migrations
make backfill                    # ~20 min: a year of station, weather, CAMS and fire data
make train                       # trains the models and writes the backtest
make forecast                    # issues the current forecast
make dev                         # API on :8000, web app on :3000
make stop                        # when you're done: stops everything, keeps the data
```

Full guide, phone testing and troubleshooting: [docs/setup.md](docs/setup.md).

## Built with AWS open source

- **[Strands Agents SDK](https://strandsagents.com)** runs the assistant: tool selection, streaming and
  the agent loop. Locally it drives a small Ollama model; deployed, the same code uses **Amazon Bedrock**
  (Amazon Nova).
- Deployment plan: FastAPI on **AWS Lambda** behind **API Gateway**, the hourly job on **EventBridge**,
  model files in **S3**, secrets in **SSM Parameter Store**, web app on **Amplify Hosting**.

## Project layout

| Directory | What lives there | Key Documentation |
| :--- | :--- | :--- |
| **[`backend/`](backend/)** | Exposure maths, XGBoost forecasting, ingestion pipelines, FastAPI service, and Strands agent | [backend/README.md](backend/README.md) |
| **[`backend/tests/`](backend/tests/)** | Unit tests for exposure calculations and Number Guard verification | [tests/test_engine.py](backend/tests/test_engine.py) |
| **[`frontend/`](frontend/)** | Next.js 16 web app: landing page, onboarding, trip planner, MapLibre GL map, assistant | [frontend/README.md](frontend/README.md) |
| **[`supabase/`](supabase/)** | PostgreSQL migration history (`migrations/`) and paste-ready standalone setup (`setup.sql`) | [docs/database.md](docs/database.md) |
| **[`contracts/`](contracts/)** | OpenAPI contract (`openapi.json`) from which frontend TypeScript types are generated | [`contracts/openapi.json`](contracts/openapi.json) |
| **[`docs/`](docs/)** | In-depth engineering documentation, architecture, mathematical method, and decisions | [📚 Docs Roadmap](#-documentation-guide-start-here) |

## Honest limits

- Delhi NCR has a few dozen reference monitors; most of a route is interpolated, and roadside levels can be
  higher than any station. Confidence scores say so.
- CPCB feeds on OpenAQ are sometimes delayed by hours or days; affected stations are model estimates.
- The exposure index is an estimate under stated assumptions, not a measured dose. Options are only compared
  within one mode of travel.
- Travel times are free-flow estimates without live traffic. Departures are planned up to 6 hours ahead.
- General guidance only, not medical advice.

## Data and credits

Station data from [OpenAQ](https://openaq.org) (CPCB, DPCC, IMD, state boards, AirNow, AirGradient).
Weather and CAMS air-quality data from [Open-Meteo](https://open-meteo.com) (CC BY 4.0, non-commercial
use) and [Copernicus CAMS](https://atmosphere.copernicus.eu). Fires from [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov).
Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright); routing by
[OSRM / FOSSGIS](https://routing.openstreetmap.de); search by [Photon](https://photon.komoot.io); tiles by
[OpenFreeMap](https://openfreemap.org).

## License

[Apache License 2.0](LICENSE)
