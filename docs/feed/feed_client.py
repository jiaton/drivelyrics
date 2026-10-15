#!/usr/bin/env python3
"""A ready-made receiver for the DriveLyrics now-playing feed (docs/feed.md).

Listens on the event stream (an outgoing connection: nothing on your side needs to be
reachable from the internet). On every "fetch" event it runs YOUR command, which reads
your player however it can and prints one JSON object in the push format, e.g.
    {"playing": true, "title": "…", "artist": "…", "duration_ms": 259000, "position_ms": 81234}
and pushes that to DriveLyrics. Python 3.9+, standard library only.

    DRIVELYRICS_TOKEN=dlf_… python3 feed_client.py --command "./read-player.sh"
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "https://drivelyrics.com"


def sse_events(response):
    """(event, data) pairs from a text/event-stream response."""
    event, data = "message", []
    for raw in response:
        line = raw.decode("utf-8").rstrip("\r\n")
        if not line:
            if data:
                yield event, "\n".join(data)
            event, data = "message", []
        elif line.startswith(":"):
            continue  # keep-alive comment
        else:
            field, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if field == "event":
                event = value
            elif field == "data":
                data.append(value)


def read_player(command: str) -> dict:
    out = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=20, check=True).stdout
    state = json.loads(out)
    if not isinstance(state, dict) or "playing" not in state:
        raise ValueError('the command must print a JSON object with at least "playing"')
    return state


def push(base: str, token: str, state: dict) -> dict:
    request = urllib.request.Request(
        f"{base}/api/feed/v1/now-playing",
        data=json.dumps(state).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "drivelyrics-feed-client/1"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def run(base: str, token: str, command: str) -> None:
    request = urllib.request.Request(
        f"{base}/api/feed/v1/events",
        headers={"Authorization": f"Bearer {token}", "Accept": "text/event-stream", "User-Agent": "drivelyrics-feed-client/1"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # keep-alives come every 15 s
        print("connected; waiting for events", file=sys.stderr)
        for event, data in sse_events(response):
            if event != "fetch":
                continue  # "stop" and "ping" need no answer; unknown events are ignored
            fetch = json.loads(data)
            try:
                state = read_player(command)
            except Exception as exc:  # noqa: BLE001 — report and wait for the next fetch
                print(f"reading the player failed: {exc}", file=sys.stderr)
                continue
            state["fetch_id"] = fetch.get("id")
            ack = push(base, token, state)
            print(f"{fetch.get('reason')}: pushed {state.get('title')!r}; next in {ack.get('next_fetch_in_ms')} ms", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--command", required=True, help="prints the player's state as one JSON object")
    parser.add_argument("--base", default=os.environ.get("DRIVELYRICS_BASE", DEFAULT_BASE))
    args = parser.parse_args()
    token = os.environ.get("DRIVELYRICS_TOKEN", "")
    if not token.startswith("dlf_"):
        sys.exit("set DRIVELYRICS_TOKEN to a feed token (Settings → Now-playing feed)")
    delay = 1
    while True:
        try:
            run(args.base.rstrip("/"), token, args.command)
            delay = 1
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                sys.exit("the token was refused: revoked, or mistyped")
            print(f"event stream: HTTP {exc.code}", file=sys.stderr)
        except (OSError, ValueError) as exc:
            print(f"event stream: {exc}", file=sys.stderr)
        time.sleep(delay)
        delay = min(delay * 2, 60)


if __name__ == "__main__":
    main()
