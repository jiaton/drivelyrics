# Now-playing feed (v1)

Show lyrics for **any** player — your car's own media system, Apple Music, Bluetooth,
radio — by telling DriveLyrics what is playing yourself. It's an alternative to linking
Spotify, and it needs no Spotify account.

DriveLyrics never holds credentials for your car or player. Reading the player happens
on your side, with your own integration (Home Assistant, a script, anything that can make
an HTTP request); DriveLyrics only receives the result. The flow:

1. While one of your DriveLyrics screens is open, DriveLyrics sends **fetch events**: on
   opening, right after the current track should have ended, and when you tap refresh.
2. Your side answers each fetch by **reading the player once and pushing** what it plays.
3. When no screen is open any more, DriveLyrics sends **stop** and goes quiet.

Your side needs no timers and no state: "on fetch, read once, push" is the whole job.

Machine-readable contract: [`feed/v1/push.schema.json`](feed/v1/push.schema.json),
[`feed/v1/push-response.schema.json`](feed/v1/push-response.schema.json),
[`feed/v1/event.schema.json`](feed/v1/event.schema.json) (JSON Schema), examples in
[`feed/v1/examples/`](feed/v1/examples/). The API's full OpenAPI document is served at
`/openapi.json`.

## Set up

1. **Settings → Now-playing feed → Create token.** Give it the name of where it will live
   ("Home Assistant"). The token (`dlf_…`) is shown once; keep it like a password. It can
   only *write* what you're playing and *receive* fetch events — nothing else.
2. Choose how fetch events reach you (below), and set up your side.
3. **Settings → Now playing from → Now-playing feed.** (With no Spotify linked, the feed is
   used automatically.)

You can create several tokens, each revocable on its own: to replace one, create the new
one, switch your side over, then revoke the old one.

## Push what is playing

```
POST /api/feed/v1/now-playing
Authorization: Bearer dlf_…
Content-Type: application/json
```

| Field | Type | |
|---|---|---|
| `playing` | bool | **Required.** |
| `title` | string | Required while playing. |
| `artist` | string | Several artists as "A, B". |
| `album` | string | |
| `duration_ms` | int | Strongly recommended: it's how DriveLyrics knows when to ask for the next track. |
| `position_ms` | int | Playback position. Omitted on a new track = 0; omitted on the same track = carry on. |
| `measured_at` | int | Unix ms when `position_ms` was read, if not "just now". Ignored when more than 5 minutes off DriveLyrics' clock. |
| `source` | string | Shown to you only ("Spotify", "Bluetooth"). |
| `fetch_id` | string | The `id` of the fetch event you are answering, if any. |

Unknown fields are ignored. You may push at any time, not only in answer to a fetch (at
most 2 pushes a second).

Responses: `200` with `{"watching": bool, "next_fetch_in_ms": int | null}` — when
DriveLyrics would next ask, for clients that don't listen to events (null: no update is
needed now); `401` unknown or revoked token; `422` invalid body (`detail` says why);
`429` too many pushes.

## Receive fetch events

Every event is one JSON object:

```json
{"type": "fetch", "id": "k3J9xQ2a", "reason": "track_ending", "at": 1760000000000}
{"type": "stop", "at": 1760000000000}
{"type": "ping", "id": "Zp0xT6qe", "at": 1760000000000}
```

- `fetch`: read the player once and push. `reason` is informational (`opened`,
  `track_ending`, `skip_check`, `paused_check`, `refresh`, `retry`; more may be added
  within v1) — treat every fetch the same.
- `stop`: no screen is open any more; nothing will be asked until the next fetch.
- `ping`: the settings page's "Test" button. No answer needed.
- Ignore event types you don't know.

There are two ways to receive them. Use either or both; the content is identical.

### Event stream (recommended: nothing to expose)

Your side opens a long-lived connection to DriveLyrics:

```
GET /api/feed/v1/events
Authorization: Bearer dlf_…
Accept: text/event-stream
```

Server-Sent Events: each event arrives as `event: <type>` plus `data: <the JSON above>`; a
keep-alive comment comes every 15 seconds. Reconnect when the connection drops (back off
up to a minute); at most 3 connections per account (`429` beyond). Because the
connection goes *out* from your side, it works from a home network with nothing
reachable from the internet.

### Webhook (optional)

**Settings → Now-playing feed → Webhook**: DriveLyrics POSTs each event as the request
body to your URL, with:

```
Content-Type: application/json
X-DriveLyrics-Event: fetch
X-DriveLyrics-Timestamp: 1760000000123
X-DriveLyrics-Signature: sha256=<hex HMAC-SHA256 of "<timestamp>.<body>" with your signing secret>
```

The signing secret is shown once when you first save the webhook (and on rotation). To
verify, recompute the HMAC over the raw body and compare in constant time; reject
timestamps more than 5 minutes old:

```python
import hashlib, hmac, time

def verify(secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    if abs(time.time() * 1000 - int(timestamp)) > 300_000:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

Rules: `https://` only, to a public internet address (no LAN, loopback or link-local
addresses; redirects are not followed); a 2xx answer within 5 seconds counts as
delivered, and the response body is never read. After 10 failures in a row the webhook
is paused until you save it again. Someone running their own DriveLyrics can allow
specific private hosts (and plain HTTP to them) with `FEED_WEBHOOK_ALLOW_HOSTS`.

## When fetches are sent, and what they cost you

Defaults ask about **once per track**:

- **opened** — a DriveLyrics screen opened (or your event-stream client reconnected while
  one is open).
- **track_ending** — 0.75 s after the current track should have ended. The answer is
  then already the next track, so one fetch per track keeps lyrics going hands-free.
- **refresh** — you tapped refresh on the lyrics screen. Taps are combined for 1.5 s, so
  skipping several tracks and tapping once costs one fetch. Even without a tap, the old
  track's end time triggers a fetch that catches up.
- **retry** — a fetch got no push within 15 s: asked again after 30 s, then every 60 s.

Optional (Settings): **skip check** every 30 or 60 s while playing (off by default), and
**paused check** every 60 or 120 s while paused (off by default).

If reading your player costs money — a Tesla Fleet API `vehicle_data` call is billed per
request, with a monthly credit shared by all your integrations — set the limits in
Settings: a **monthly budget** of fetches (default 1000; when used up, automatic fetches
stop and refresh asks you to confirm) and an **hourly cap** (default 60, a guard against
bugs). Only fetches that reached your side are counted.

## Recipes

### Try it with curl

```sh
curl -sS https://drivelyrics.com/api/feed/v1/now-playing \
  -H "Authorization: Bearer $DRIVELYRICS_TOKEN" -H 'Content-Type: application/json' \
  -d '{"playing": true, "title": "Bohemian Rhapsody", "artist": "Queen", "duration_ms": 354000, "position_ms": 0}'
```

With Now playing from set to the feed, an open DriveLyrics screen shows the song at once.

### Any player, no exposed ports: `feed_client.py`

[`feed/feed_client.py`](feed/feed_client.py) (Python 3.9+, standard library only) listens
on the event stream and, on every fetch, runs a command you provide that prints the
player's state as one JSON object in the push format:

```sh
DRIVELYRICS_TOKEN=dlf_… python3 feed_client.py --command "./read-player.sh"
```

### Home Assistant blueprint

Needs Home Assistant reachable over HTTPS from the internet (your own domain, or Nabu
Casa's cloud webhooks) and a `media_player` entity for the player — e.g. the Tesla Fleet
integration's vehicle media player. On each fetch the automation asks the integration to
read the player once (for a Tesla: one `vehicle_data` call), waits a few seconds and
pushes what it plays. Checked in a car with Spotify playing (2026-10-27): title,
artist, album, duration and position all arrive; position is whole seconds.

1. Once, in `configuration.yaml` (then restart Home Assistant):

   ```yaml
   rest_command:
     drivelyrics_push:
       url: https://drivelyrics.com/api/feed/v1/now-playing
       method: POST
       headers:
         Authorization: !secret drivelyrics_feed_auth   # "Bearer dlf_…" in secrets.yaml
       content_type: application/json
       payload: "{{ payload }}"
   ```

2. Import the blueprint:
   [`feed/homeassistant/drivelyrics_feed.yaml`](feed/homeassistant/drivelyrics_feed.yaml)
   (Settings → Automations & scenes → Blueprints → Import blueprint, with the URL
   `https://github.com/jiaton/drivelyrics/blob/main/docs/feed/homeassistant/drivelyrics_feed.yaml`),
   and create an automation from it: pick the media player, and as webhook ID a long
   random string.
3. In DriveLyrics, set the webhook URL to
   `https://<your-home-assistant>/api/webhook/<that webhook ID>` and press Test — the
   automation's trace shows the ping arriving (pings are not answered).

Home Assistant webhooks can't check the signature; the random webhook ID is what keeps
the URL private. Media players don't report when their position was read, so the push
uses the entity's `last_reported` time (when Home Assistant last received its state) as
`measured_at`.

## Versioning

Everything above is v1 (`/api/feed/v1/…`). Within v1, fields and event types are only
ever *added*: ignore what you don't know, and don't rely on the order of fields. An
incompatible change would come as v2, served alongside v1 for a transition period.
