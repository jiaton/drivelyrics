"""Test settings, set before anything imports app.core.config (which reads them once).
Environment variables win over backend/.env, which in a dev checkout is a symlink to
the production values — tests must never touch those."""

import os
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

# RAM-backed when available: on the NAS every fsync to disk costs ~0.7s.
_TMP = tempfile.mkdtemp(prefix="lyric-test-", dir="/dev/shm" if os.path.isdir("/dev/shm") else None)

os.environ.update(
    {
        "ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "DATABASE_PATH": os.path.join(_TMP, "app.db"),
        "PUBLIC_BASE_URL": "http://testserver",
        "DEV_LOGIN": "true",
        "OWNER_EMAIL": "owner@example.com",
        "GOOGLE_CLIENT_ID": "",
        "GOOGLE_CLIENT_SECRET": "",
        "SPOTIFY_CLIENT_ID": "legacy-client-id",
        "SPOTIFY_CLIENT_SECRET": "legacy-client-secret",
    }
)


@pytest.fixture
def tmp_path():
    return Path(tempfile.mkdtemp(dir=_TMP))


@pytest.fixture
def app_client():
    """A fresh browser (own cookie jar) against the app, lifespan included."""
    from fastapi.testclient import TestClient

    from app.main import app

    clients = []

    def make():
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)


def sign_in(client, email: str) -> dict:
    resp = client.post("/api/auth/dev-login", json={"email": email})
    assert resp.status_code == 200, resp.text
    return resp.json()
