from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Where browsers reach this app. OAuth redirect URIs (Google, every user's own
    # Spotify app) and the pairing QR code are all built from it.
    public_base_url: str = "https://drivelyrics.com"

    # Fernet key encrypting Spotify client secrets and tokens at rest.
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key: str

    # Google OAuth client (Web). Empty = Google login disabled.
    google_client_id: str = ""
    google_client_secret: str = ""

    # Owner account: the pre-multi-user data (Spotify link, preferences) is migrated to
    # this email, which is also the one admin. Matched on first Google login.
    owner_email: str = ""

    # Local development only: enables POST /api/auth/dev-login, which signs in as any
    # email without Google. Never set in production.
    dev_login: bool = False

    # Pre-multi-user Spotify app credentials. Read once, by the migration that moves the
    # owner's link to their account (core/migrations.py), then unused.
    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    # A NeteaseCloudMusicApi-compatible service (search + lyric endpoints). Optional:
    # empty = NetEase is not used and LRCLIB is the only lyrics source. Not shipped in
    # the public repository (see README); drivelyrics.com runs one as a sidecar.
    netease_api_base_url: str = ""
    lrclib_base_url: str = "https://lrclib.net"

    database_path: str = "/app/data/lyric.db"
    poll_interval_seconds: float = 4.0

    @property
    def secure_cookies(self) -> bool:
        return self.public_base_url.startswith("https://")


settings = Settings()
