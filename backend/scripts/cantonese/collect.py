"""Collect a labelled corpus for train.py from a NeteaseCloudMusicApi-compatible
service (NetEase romanizes Cantonese lyrics; that's the label):

    python collect.py http://your-netease-api:3000 OUT_DIR

Slow on purpose — one request every PACE seconds — and it stops at the first sign of
rate limiting instead of retrying, so a service that also serves live lyrics is never
put at risk. Resumable: songs already in OUT_DIR/corpus.jsonl are skipped. 1450 songs
took ~2.5 h on 2026-10-11. Playlists: four Cantonese, four Mandarin (the label comes
from the romanization, not from the playlist)."""
import json, os, sys, time
import httpx

PACE = 6.0
PLAYLISTS = {  # id: which list it came from (the label is NetEase's romalrc, not this)
    368254901: "canto", 2237551001: "canto", 7610827069: "canto", 13016484326: "canto",
    6847295283: "mando", 2893945938: "mando", 420646708: "mando", 2704872117: "mando",
}
BASE_URL, OUT_DIR = sys.argv[1], sys.argv[2]
OUT, STATUS = os.path.join(OUT_DIR, "corpus.jsonl"), os.path.join(OUT_DIR, "status.txt")
c = httpx.Client(base_url=BASE_URL, timeout=20)

def status(msg):
    open(STATUS, "w").write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    print(msg, flush=True)

def get(path, **params):
    time.sleep(PACE)
    r = c.get(path, params=params)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != 200 or body.get("code") not in (200, None):
        raise RuntimeError(f"{path} -> HTTP {r.status_code}, code {body.get('code')}, {str(body.get('msg') or body.get('message') or '')[:80]}")
    return body

done = set()
if os.path.exists(OUT):
    for line in open(OUT):
        done.add(json.loads(line)["id"])

try:
    lists = {}
    for pid, lang in PLAYLISTS.items():
        tracks = get("/playlist/track/all", id=pid, limit=600).get("songs") or []
        lists[pid] = [(t["id"], t["name"], [a.get("name") or "" for a in t.get("ar") or []], lang) for t in tracks]
        status(f"playlist {pid} ({lang}): {len(tracks)} tracks")
    # Interleave Cantonese and Mandarin lists so a run cut short is still balanced.
    queue, seen = [], set()
    iters = [iter(v) for v in lists.values()]
    while iters:
        for it in list(iters):
            t = next(it, None)
            if t is None:
                iters.remove(it)
            elif t[0] not in seen:
                seen.add(t[0]); queue.append(t)
    todo = [t for t in queue if t[0] not in done]
    status(f"{len(queue)} unique songs, {len(done)} already done, {len(todo)} to go (~{len(todo) * PACE / 3600:.1f} h)")
    with open(OUT, "a") as f:
        for i, (sid, name, artists, lang) in enumerate(todo, 1):
            body = get("/lyric", id=sid)
            lrc = (body.get("lrc") or {}).get("lyric") or ""
            roma = bool((body.get("romalrc") or {}).get("lyric"))
            f.write(json.dumps({"id": sid, "name": name, "artists": artists, "list": lang, "roma": roma, "lrc": lrc}, ensure_ascii=False) + "\n")
            f.flush()
            if i % 50 == 0:
                status(f"{len(done) + i}/{len(queue)} done")
    status(f"DONE {len(queue)} songs")
except Exception as e:
    status(f"STOPPED: {e!r}")
