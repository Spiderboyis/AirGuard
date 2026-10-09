#!/usr/bin/env python3
"""Concatenate supabase/migrations/*.sql into supabase/setup.sql.

setup.sql is what you paste into the SQL editor of a fresh hosted Supabase project. Migrations stay
the source of truth: never edit setup.sql by hand, add a new migration and re-run `make setup-sql`.

    python scripts/build_setup_sql.py          # write supabase/setup.sql
    python scripts/build_setup_sql.py --check  # exit 1 if setup.sql is out of date (used in CI)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
OUT = ROOT / "supabase" / "setup.sql"

HEADER = """\
-- =============================================================================================
-- AirGuard: full database setup for a fresh Supabase project.
--
-- GENERATED FILE. Do not edit by hand. Source: supabase/migrations/*.sql
-- Regenerate with: make setup-sql
--
-- How to use: open your project's SQL editor in the Supabase dashboard, paste this whole file,
-- and run it. It is idempotent, so running it again on an existing project is safe.
-- Migrations included (in order):
{listing}
-- =============================================================================================
"""


def build() -> str:
    files = sorted(MIGRATIONS.glob("*.sql"))
    listing = "\n".join(f"--   {f.name}" for f in files)
    parts = [HEADER.format(listing=listing)]
    for f in files:
        parts.append(f"\n-- ---- {f.name} " + "-" * max(0, 86 - len(f.name)) + "\n")
        parts.append(f.read_text().strip() + "\n")
    return "".join(parts)


def main() -> int:
    content = build()
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text() != content:
            print("supabase/setup.sql is out of date; run `make setup-sql`.", file=sys.stderr)
            return 1
        print("supabase/setup.sql is up to date.")
        return 0
    OUT.write_text(content)
    print(f"wrote {OUT.relative_to(ROOT)} from {len(list(MIGRATIONS.glob('*.sql')))} migrations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
