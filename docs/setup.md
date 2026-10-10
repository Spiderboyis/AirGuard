# Local setup

Everything runs on your machine: Postgres (local Supabase in Docker or Podman), the API, the web app,
and a small language model through Ollama. Only one free API key is required.

## Prerequisites

| Tool | Version | Notes |
| --- | --- | --- |
| Python | 3.12 | `python3.12 -m venv` must work |
| Node.js | 20+ | npm comes with it |
| Docker **or** Podman | any recent | For local Supabase. With Podman, enable the socket: `systemctl --user enable --now podman.socket` |
| Ollama | 0.5+ | For the assistant. Optional: without it the assistant falls back to verified, template explanations |

The Makefile points the Supabase CLI at Podman's socket automatically when Docker isn't running.

## 1. Install

```bash
git clone <your fork> airguard && cd airguard
make setup          # venv + backend (editable) + frontend deps + pulls qwen3:1.7b
```

## 2. Keys

Create `.env.local` in the repo root (git-ignored). Settings in it override `.env`.

```text
OPENAQ_API_KEY=...      # required
FIRMS_MAP_KEY=...       # optional, adds crop-fire features
```

**OpenAQ** (station data): register at <https://explore.openaq.org/register>, verify your email, sign in,
then open your account page and copy the API key.

**NASA FIRMS** (fires, optional): enter your email at <https://firms.modaps.eosdis.nasa.gov/api/map_key/>;
the key arrives by email within a minute.

Routing (OSRM), place search (Photon), weather and CAMS (Open-Meteo) and map tiles (OpenFreeMap) need no
key.

## 3. Database

```bash
make db-start       # starts local Supabase and applies supabase/migrations
```

Studio (a database UI) is at <http://127.0.0.1:54323>. The backend connects with `DATABASE_URL`
(default `postgresql://postgres:postgres@127.0.0.1:54322/postgres`). See [database.md](database.md) for
migrations and setting up a hosted project.

## 4. Data and model

```bash
make backfill       # ~20 min: a year of PM2.5 (OpenAQ), weather + CAMS, fires
make train          # ~5 min: trains six models, writes the backtest
make forecast       # fetches the latest hour and issues a forecast
```

## 5. Run

```bash
make dev            # API on :8000 and web on :3000
make hourly         # optional, in another terminal: refresh forecasts every hour
```

Open <http://localhost:3000>. The API docs are at <http://localhost:8000/docs>.

## 6. Stop

```bash
make stop           # stops web, API, hourly job, unloads the LLM, stops Supabase
```

Data stays in the local database; `make start` (database + API + web) or `make db-start && make dev`
brings everything back. If you started a process yourself in a terminal, `Ctrl+C` there works too.

### On your phone (same Wi-Fi)

```bash
cd backend && ../.venv/bin/uvicorn airguard.api.main:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev -- -H 0.0.0.0
```

Set `NEXT_PUBLIC_API_URL=http://<laptop-ip>:8000` in `frontend/.env.local` and add
`http://<laptop-ip>:3000` to `ALLOWED_ORIGINS` in `.env.local`.

## Choosing the language model

The default is `qwen3:1.7b` (1.4 GB), which fits in 4 GB of VRAM. Any Ollama model with tool calling
works: set `OLLAMA_MODEL` in `.env.local`. Larger models (`qwen3:4b`, `llama3.1:8b`) answer more
naturally; smaller ones are steadied by the narrow tool sets and the number guard. Set `LLM_BACKEND=none`
to run without a model.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `database_unavailable` from the API | `make db-start`; check `make db-status` |
| `OpenAQ rejected the API key` | Check `OPENAQ_API_KEY` in `.env.local` |
| Many stations shown as *estimated* | CPCB feeds on OpenAQ are delayed; the model estimates those stations. Run `make forecast` later |
| `forecast_unavailable` | No forecast issued yet: `make forecast` |
| Assistant answers "explained without the language model" | Ollama isn't running or the model isn't pulled: `ollama serve`, `ollama pull qwen3:1.7b` |
| Supabase CLI can't find Docker | Start Podman's socket (see prerequisites) or Docker |
