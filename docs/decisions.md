# Decision log

Short records of choices that shaped the build, newest last. Each says what was decided and why.

### Local-first, deploy later
Everything (database, API, web, LLM) runs locally first. AWS deployment is a separate step once the
local build is solid. The hackathon scores local and deployed projects equally, and Strands Agents SDK
(an AWS open-source project) satisfies the "AWS open source tool" rule either way.

### Real data only
No synthetic data, even for development. Station data comes from OpenAQ (free key), everything else from
keyless services.

### Postgres access through psycopg, not the Supabase REST API
Bulk loads (hundreds of thousands of rows) and training reads are far faster over a direct connection,
and the backend then needs no Supabase service key. Row-level security stays on with no policies, so the
public REST API exposes nothing.

### OSRM (FOSSGIS) instead of OpenRouteService
The FOSSGIS OSRM servers offer foot, bike and car profiles with alternatives and no key. When they return
too few distinct routes, AirGuard asks for routes through offset via-points. Responses are cached.

### CPCB feed delay is a first-class case
On 9 Oct 2026 every CPCB station on OpenAQ stopped at 7 Oct 14:30 UTC while low-cost sensors and the US
Embassy monitor stayed current. Rather than hide this, the model is trained with 25% of rows' own-station
history blanked, uses CAMS and neighbours as covariates, reports a separate "delayed feed" backtest, and
the UI labels those stations as estimated.

### CAMS as a covariate and a baseline
Open-Meteo's CAMS PM2.5 is coarse (~45 km over India) but always current and forecasts ahead. It is used
as an input (the model learns each station's bias against it) and reported as a third baseline, so the
evaluation shows what local station data adds.

### One model per horizon, log target, split-conformal intervals
Errors scale with concentration, so the target is log-PM2.5. Intervals come from the 10th/90th
percentiles of actual ÷ predicted on a calibration week, separately for normal and delayed modes.

### Sensitivity changes the decision, not the estimate
Exposure numbers are identical for every user. Sensitivity only sets how many minutes a 10% reduction is
worth (4 / 7 / 10). Waiting counts half because it can happen indoors.

### Steering a 1.7B-parameter local model
`qwen3:1.7b` fits a 4 GB GPU but chooses tools poorly from long lists. With a trip on screen the agent
gets two tools; identical repeat calls return the earlier result with a nudge; every number is checked
against tool outputs; any failure falls back to a deterministic explanation that says so. On AWS the same
code runs against Amazon Bedrock.

### Pinned backend dependencies
pip's resolver stalled for minutes on the open-ended requirements in `pyproject.toml`. Setup and CI install
the exact tested versions from `backend/requirements.lock`, then the package itself with `--no-deps`.

### Repository and licence
The code lives in the team repository (github.com/Spiderboyis/AirGuard), which is Apache-2.0; the
project's README and `pyproject.toml` follow that licence.

### Landing page shows a real result
The hero is the actual analysis for one demo ride: the forecast along the route over the next hours, with
the ride drawn as a window of its own duration. Earlier attempts (stat cards, then per-departure colour
strips) didn't explain why leaving later helps; a window sliding along the day's air does.

### Next.js 16 with cache components, shadcn/ui on Base UI
Interactive pages are client components fed by the API. The persisted profile is applied on the first
client render to avoid hydration mismatches. MapLibre's worker is served from `/public` because the
bundler can't resolve its URL.
