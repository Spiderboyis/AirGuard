#!/usr/bin/env python3
"""Write the API contract (contracts/openapi.json) from the FastAPI app, without starting a server."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from airguard.api.main import app  # noqa: E402

out = ROOT / "contracts" / "openapi.json"
out.write_text(json.dumps(app.openapi(), indent=2) + "\n")
print(f"wrote {out.relative_to(ROOT)}")
