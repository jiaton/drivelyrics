"""The committed contract files must match the code, or the frontend's generated types
(and any external client built from them) silently drift. Regenerate with the script
named in each failure message."""

import json
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def test_openapi_document_is_current():
    committed = json.loads((ROOT / "frontend" / "src" / "lib" / "openapi.json").read_text(encoding="utf-8"))
    app.openapi_schema = None
    assert committed == app.openapi(), "stale: run `poetry run python scripts/export_openapi.py`, then `npm run gen:api` in frontend/"
