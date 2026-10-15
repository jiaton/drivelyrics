from tests.conftest import sign_in

PLAYING = {"playing": True, "title": "富士山下", "artist": "陳奕迅", "duration_ms": 259000, "position_ms": 1000}


def new_token(client, name="Home Assistant") -> str:
    resp = client.post("/api/feed/tokens", json={"name": name})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def test_push_with_a_token(app_client):
    a = app_client()
    sign_in(a, "feed-push@example.com")
    token = new_token(a)
    assert token.startswith("dlf_")
    resp = a.post("/api/feed/v1/now-playing", json=PLAYING, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200 and resp.json() == {"watching": False, "next_fetch_in_ms": None}
    status = a.get("/api/feed/status").json()
    assert status["enabled"] and status["last_push"]["title"] == "富士山下"


def test_tokens_are_shown_once_and_revocable_only_by_their_owner(app_client):
    a, b = app_client(), app_client()
    sign_in(a, "feed-tok-a@example.com")
    sign_in(b, "feed-tok-b@example.com")
    token = new_token(a)
    listed = a.get("/api/feed/tokens").json()["tokens"]
    assert len(listed) == 1 and token not in str(listed) and listed[0]["prefix"] == token[:8]
    assert b.delete(f"/api/feed/tokens/{listed[0]['id']}").status_code == 404
    assert a.delete(f"/api/feed/tokens/{listed[0]['id']}").status_code == 200
    resp = a.post("/api/feed/v1/now-playing", json=PLAYING, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_bad_tokens_bad_bodies_and_floods(app_client):
    a = app_client()
    sign_in(a, "feed-bad@example.com")
    token = new_token(a)
    auth = {"Authorization": f"Bearer {token}"}
    assert a.post("/api/feed/v1/now-playing", json=PLAYING).status_code == 401
    assert a.post("/api/feed/v1/now-playing", json=PLAYING, headers={"Authorization": "Bearer dlf_nope"}).status_code == 401
    assert a.post("/api/feed/v1/now-playing", json={"playing": True}, headers=auth).status_code == 422  # no title
    extra = PLAYING | {"future_field": 1}  # unknown fields are ignored, not refused
    assert a.post("/api/feed/v1/now-playing", json=extra, headers=auth).status_code == 200
    assert a.post("/api/feed/v1/now-playing", json=PLAYING, headers=auth).status_code == 429


def test_a_feed_token_is_not_a_session(app_client):
    a, c = app_client(), app_client()
    sign_in(a, "feed-scope@example.com")
    token = new_token(a)
    assert c.get("/api/feed/status", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert c.get("/api/preferences", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_settings_and_webhook_validation(app_client):
    a = app_client()
    sign_in(a, "feed-settings@example.com")
    assert a.put("/api/feed/settings", json={"skip_check_s": 45}).status_code == 422
    body = a.put("/api/feed/settings", json={"skip_check_s": 30, "monthly_budget": 500}).json()
    assert (body["skip_check_s"], body["monthly_budget"], body["paused_check_s"]) == (30, 500, 0)
    resp = a.put("/api/feed/webhook", json={"url": "https://10.0.0.1/api/webhook/x"})
    assert resp.status_code == 422 and "public" in resp.json()["detail"]
    assert a.put("/api/feed/webhook", json={"url": "http://93.184.216.34/hook"}).status_code == 422
    saved = a.put("/api/feed/webhook", json={"url": "https://93.184.216.34/hook"}).json()
    assert saved["secret"]  # first save: a new secret, shown once
    again = a.put("/api/feed/webhook", json={"url": "https://93.184.216.34/other"}).json()
    assert again["secret"] is None  # the existing secret stays
    assert a.get("/api/feed/settings").json()["webhook_url"] == "https://93.184.216.34/other"


def test_sources_follow_what_is_set_up(app_client):
    a = app_client()
    sign_in(a, "feed-sources@example.com")
    assert a.get("/api/now-playing/sources").json()["effective"] is None
    assert a.get("/api/now-playing/stream").status_code == 409
    new_token(a)
    info = a.get("/api/now-playing/sources").json()
    assert (info["selected"], info["effective"], info["feed_enabled"]) == ("spotify", "feed", True)  # only the feed is set up
    assert a.put("/api/now-playing/source", json={"source": "feed"}).json()["selected"] == "feed"
    assert a.put("/api/now-playing/source", json={"source": "other"}).status_code == 422


def test_sync_offset_preference(app_client):
    a = app_client()
    sign_in(a, "feed-offset@example.com")
    assert a.get("/api/preferences").json()["sync_offset_ms"] == 0
    assert a.put("/api/preferences", json={"sync_offset_ms": 750}).json()["sync_offset_ms"] == 750
    assert a.put("/api/preferences", json={"sync_offset_ms": 9000}).status_code == 422


def test_account_deletion_removes_the_feed(app_client):
    a = app_client()
    sign_in(a, "feed-delete@example.com")
    token = new_token(a)
    assert a.delete("/api/account").status_code == 200
    c = app_client()
    assert c.post("/api/feed/v1/now-playing", json=PLAYING, headers={"Authorization": f"Bearer {token}"}).status_code == 401
