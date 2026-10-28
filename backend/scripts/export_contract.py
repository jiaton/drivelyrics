"""Write the now-playing feed's public contract as JSON Schema into docs/feed/v1/, next
to docs/feed.md. tests/test_contract.py fails while these are stale.

    poetry run python scripts/export_contract.py"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT.parent / "docs" / "feed" / "v1"


def schemas() -> dict[str, str]:
    from app.feed.schemas import FeedEvent, FeedMe, FeedPush, FeedPushAck, LinkPoll, LinkPollResult, LinkStart, LinkStarted

    files = {
        "push.schema.json": FeedPush,
        "push-response.schema.json": FeedPushAck,
        "event.schema.json": FeedEvent,
        "me.schema.json": FeedMe,
        "link-start.schema.json": LinkStart,
        "link-started.schema.json": LinkStarted,
        "link-poll.schema.json": LinkPoll,
        "link-poll-result.schema.json": LinkPollResult,
    }
    requests = (FeedPush, LinkStart, LinkPoll)
    out = {}
    for name, model in files.items():
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"https://drivelyrics.com/docs/feed/v1/{name}"}
        schema |= model.model_json_schema(mode="validation" if model in requests else "serialization")
        out[name] = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    return out


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, body in schemas().items():
        (OUT / name).write_text(body, encoding="utf-8")
        print(f"wrote {OUT / name}")
