# Security policy

## Reporting a vulnerability

Please don't open a public issue. Use the repository's **private vulnerability reporting** (Security →
Report a vulnerability) with steps to reproduce. We aim to reply within a few days.

## How AirGuard handles secrets and data

- API keys live in `.env.local` locally (git-ignored) and in AWS SSM Parameter Store when deployed. Only
  `.env.example` files are committed.
- The web app never talks to the database. Row-level security is enabled on every table with no
  policies, so Supabase's public `anon` key can read nothing.
- The traveller's profile is stored only in their browser's local storage. Trips sent to the API are
  stored without any user identifier.
- Every request is validated server-side (coordinates must be inside Delhi NCR, modes and limits are
  enumerated and bounded). The assistant endpoints are rate-limited per IP.
- CORS is restricted to the configured web origins.
