from app.feed import routes as feed_routes
from app.feed.linking import LINK_TTL_SECONDS, LinkRegistry
from tests.conftest import sign_in
from tests.test_feed_api import PLAYING


class Clock:
    def __init__(self):
        self.at = 1_760_000_000.0

    def __call__(self):
        return self.at


def test_registry_hands_out_a_decision_once():
    links = LinkRegistry()
    code, secret = links.start("Home Assistant")
    assert links.poll(secret) == ("pending", None)
    assert links.approve(code.lower(), "dlf_x")  # codes are case- and dash-insensitive
    assert not links.approve(code, "dlf_y")  # already decided
    assert links.poll(secret) == ("approved", "dlf_x")
    assert links.poll(secret) == ("expired", None)  # handed out once


def test_registry_denial_and_expiry():
    clock = Clock()
    links = LinkRegistry(clock=clock)
    code, secret = links.start("x")
    assert links.deny(code) and links.poll(secret) == ("denied", None)
    code, secret = links.start("x")
    clock.at += LINK_TTL_SECONDS + 1
    assert links.pending(code) is None and not links.approve(code, "dlf_x")
    assert links.poll(secret) == ("expired", None)


def _start(client, name="Home Assistant"):
    feed_routes._link_start_limit._last.clear()
    resp = client.post("/api/feed/v1/link", json={"client_name": name})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _poll(client, secret):
    feed_routes._link_poll_limit._last.clear()
    return client.post("/api/feed/v1/link/poll", json={"poll_secret": secret}).json()


def test_link_flow_gives_the_receiver_a_working_token(app_client):
    receiver, user = app_client(), app_client()
    sign_in(user, "feed-link@example.com")
    started = _start(receiver)
    assert "-" in started["code"] and started["verify_url"].endswith(started["code"].replace("-", ""))
    assert _poll(receiver, started["poll_secret"]) == {"status": "pending", "token": None}

    info = user.get("/api/feed/link", params={"code": started["code"]}).json()
    assert info == {"code": started["code"], "client_name": "Home Assistant"}
    approved = user.post("/api/feed/link/approve", json={"code": started["code"]}).json()
    assert approved["name"] == "Home Assistant"

    result = _poll(receiver, started["poll_secret"])
    assert result["status"] == "approved" and result["token"].startswith("dlf_")
    auth = {"Authorization": f"Bearer {result['token']}"}
    assert receiver.post("/api/feed/v1/now-playing", json=PLAYING, headers=auth).status_code == 200
    me = receiver.get("/api/feed/v1/me", headers=auth).json()
    assert me == {"token_name": "Home Assistant", "feed_selected": True}  # no Spotify: the feed is shown
    assert _poll(receiver, started["poll_secret"])["status"] == "expired"


def test_link_needs_a_signed_in_approver_and_a_live_code(app_client):
    receiver, stranger = app_client(), app_client()
    started = _start(receiver)
    assert stranger.post("/api/feed/link/approve", json={"code": started["code"]}).status_code == 401
    sign_in(stranger, "feed-link-deny@example.com")
    assert stranger.post("/api/feed/link/deny", json={"code": started["code"]}).status_code == 200
    assert stranger.post("/api/feed/link/approve", json={"code": started["code"]}).status_code == 404
    assert _poll(receiver, started["poll_secret"]) == {"status": "denied", "token": None}
    assert stranger.get("/api/feed/link", params={"code": "NOPE-NOPE"}).status_code == 404


def test_link_endpoints_are_rate_limited(app_client):
    receiver = app_client()
    started = _start(receiver)
    assert receiver.post("/api/feed/v1/link", json={"client_name": "x"}).status_code == 429
    _poll(receiver, started["poll_secret"])
    assert receiver.post("/api/feed/v1/link/poll", json={"poll_secret": started["poll_secret"]}).status_code == 429


def test_me_rejects_bad_tokens(app_client):
    assert app_client().get("/api/feed/v1/me", headers={"Authorization": "Bearer dlf_nope"}).status_code == 401
