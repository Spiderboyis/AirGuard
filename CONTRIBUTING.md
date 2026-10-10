# Contributing to AirGuard

Thanks for helping people in Delhi breathe a little less smoke. Issues and pull requests are welcome.

## Getting set up

Follow [docs/setup.md](docs/setup.md). In short: `make setup`, add an OpenAQ key to `.env.local`,
`make db-start backfill train forecast`, then `make dev`.

## Before you open a pull request

```bash
make check          # backend tests, ruff, eslint, TypeScript, and the setup.sql check
```

- **Engine changes** (`backend/airguard/engine`) need a unit test. The engine must stay free of network
  and database calls.
- **New assumptions** go in `engine/assumptions.py` (they're shown to users via `/meta`) and in
  `docs/methodology.md`.
- **Schema changes** are new files in `supabase/migrations/`, written idempotently. Run `make setup-sql`
  so `supabase/setup.sql` stays in sync. See [docs/database.md](docs/database.md).
- **API changes** must update the contract: `make contracts` regenerates `contracts/openapi.json` and the
  frontend types.
- **Agent tools** must return data the number guard can check. Never let the model produce a number that
  didn't come from a tool.
- **UI**: keep colour for meaning (the air-quality scale); everything else is paper and ink. Every
  number on screen should have a unit and, where it's a forecast, a confidence or range nearby.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/): `feat(engine): ...`, `fix(api): ...`,
`docs: ...`. Keep commits small and focused.

## Reporting data problems

If a station looks wrong, check it on [OpenAQ Explore](https://explore.openaq.org) first, then open an
issue with the station name, time (IST) and what you expected.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
