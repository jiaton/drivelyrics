from typing import Protocol

from app.feed.schemas import DeliveryResult


class WebhookSenderPort(Protocol):
    """Delivers one event to a user's webhook. Never raises: a failure is a result."""

    async def check(self, url: str) -> str | None:
        """None if events may be sent to this URL, else why not (for the settings form)."""
        ...

    async def deliver(self, url: str, secret: str, body: bytes, event_type: str) -> DeliveryResult: ...
