# AirGuard web app

Next.js 16 (App Router), Tailwind CSS 4, shadcn/ui on Base UI, Motion, MapLibre GL and Recharts.

```bash
npm install          # also copies MapLibre's worker into public/maplibre
npm run dev          # http://localhost:3000 (next free port if taken); API at NEXT_PUBLIC_API_URL
npm run lint && npm run typecheck   # typecheck runs `next typegen` first
npm run gen:types    # regenerate src/lib/api-types.ts from ../contracts/openapi.json
```

## Layout

| Path | Contents |
| --- | --- |
| `src/app/page.tsx` | Landing page: live ride-window chart, annotated route, evidence |
| `src/app/welcome/` | Onboarding (profile saved in local storage) |
| `src/app/plan/` | Trip planner: form, map, recommendation, departure chart, routes, assistant |
| `src/app/evidence/` | Backtest results |
| `src/app/method/` | Method and assumptions, rendered from the API's `/meta` |
| `src/components/air/` | Air-quality primitives: exposure strip, risk badge, confidence meter, legend, CPCB band and scroll indicator |
| `src/components/landing/` | Landing-page figures: ride-window chart and annotated route |
| `src/components/map/` | MapLibre map with stations and PM2.5-coloured route segments |
| `src/components/plan/` | Planner panels and the streaming assistant |
| `src/lib/` | Typed API client, AQ scale, formatting, profile store |

## Design rules

- Paper and ink neutrals; colour only for meaning, using CPCB's PM2.5 bands (`src/lib/aq.ts`).
- Newsreader for headlines and big numbers, IBM Plex Sans for UI, Plex Mono for data.
- Every forecast number sits next to a unit and a confidence or range.
- Light and dark themes; check both.

Environment: copy `.env.example` to `.env.local`.
