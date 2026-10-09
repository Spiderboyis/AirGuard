import os
import tempfile
from pathlib import Path

_ROOT = Path(tempfile.mkdtemp(prefix="airguard-tests-"))
os.environ["LOCAL"] = "1"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_KEY"] = ""
os.environ["OPENAQ_API_KEY"] = ""
os.environ["ORS_API_KEY"] = ""
os.environ["FIRMS_MAP_KEY"] = ""
os.environ["AIRGUARD_STRAIGHT_ROUTES"] = ""
os.environ["AIRGUARD_DB"] = str(_ROOT / "default.db")
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"
os.environ["MODEL_VERSION"] = "test"

import pytest


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AIRGUARD_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")
    from common.config import cfg
    cfg.cache_clear()
    from common import db
    db.reset_connection()
    from api import service
    from api.main import reset_rate_limit
    service._CACHE.clear()
    reset_rate_limit()
    yield
