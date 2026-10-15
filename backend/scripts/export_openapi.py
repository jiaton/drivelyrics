"""Write the API's OpenAPI document to frontend/src/lib/openapi.json, the source the
frontend's types are generated from (frontend: npm run gen:api). Run after changing
any request/response schema; tests/test_contract.py fails while the file is stale.

    poetry run python scripts/export_openapi.py"""

import json
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())  # settings needs one; unused here

OUT = ROOT.parent / "frontend" / "src" / "lib" / "openapi.json"


def document() -> str:
    from app.main import app

    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUT.write_text(document(), encoding="utf-8")
    print(f"wrote {OUT}")
