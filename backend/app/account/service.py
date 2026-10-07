"""Deleting an account touches every domain that keeps per-user rows; this module is
only the order of those calls (rows referencing users.id before the user itself)."""

from sqlmodel import Session

from app.auth.service import delete_user
from app.lyrics.service import forget_user
from app.preferences.service import delete_preferences
from app.spotify.service import PollerRegistry, SpotifyAccounts


def delete_account(db: Session, user_id: int, accounts: SpotifyAccounts, pollers: PollerRegistry) -> None:
    pollers.restart(user_id)  # stop polling Spotify for them; open screens reconnect and get 401
    # `db` already holds a read snapshot (it looked the user up). SQLite in WAL mode won't
    # let a connection write from a snapshot that another connection has since committed
    # past ("database is locked"), so `db`'s writes go before SpotifyAccounts, which
    # commits on its own connection; delete_user then starts a fresh transaction.
    forget_user(db, user_id)
    delete_preferences(db, user_id)
    db.commit()  # end db's transaction even if delete_preferences found nothing to write
    accounts.remove_app(user_id)  # Spotify app credentials + tokens
    delete_user(db, user_id)
