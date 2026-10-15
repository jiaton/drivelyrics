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


def _load_script(path: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_feed_json_schemas_are_current():
    exporter = _load_script(ROOT / "backend" / "scripts" / "export_contract.py")
    for name, body in exporter.schemas().items():
        committed = (ROOT / "docs" / "feed" / "v1" / name).read_text(encoding="utf-8")
        assert committed == body, f"docs/feed/v1/{name} is stale: run `poetry run python scripts/export_contract.py`"


def test_feed_examples_are_valid():
    from app.feed.schemas import FeedEvent, FeedPush, FeedPushAck

    examples = ROOT / "docs" / "feed" / "v1" / "examples"
    kinds = {"push-response": FeedPushAck, "push": FeedPush, "event": FeedEvent}
    files = sorted(examples.glob("*.json"))
    assert files
    for path in files:
        model = next(m for prefix, m in kinds.items() if path.stem.startswith(prefix))
        model.model_validate_json(path.read_text(encoding="utf-8"))


def test_feed_client_parses_the_event_stream():
    client = _load_script(ROOT / "docs" / "feed" / "feed_client.py")
    stream = [b": ping\r\n", b"\r\n", b"event: fetch\r\n", b'data: {"type":"fetch","id":"x"}\r\n', b"\r\n", b"event: stop\n", b"data: {}\n", b"\n"]
    assert list(client.sse_events(iter(stream))) == [("fetch", '{"type":"fetch","id":"x"}'), ("stop", "{}")]
