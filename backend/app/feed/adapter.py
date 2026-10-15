import asyncio
import hashlib
import hmac
import socket
import time
from collections.abc import Awaitable, Callable

import httpx

from app.core.config import settings
from app.feed.netguard import Target, UnsafeTarget, allow_list, parse_target, pick_address
from app.feed.ports import WebhookSenderPort
from app.feed.schemas import DeliveryResult

TIMEOUT_SECONDS = 5.0

Resolver = Callable[[str, int], Awaitable[list[str]]]


async def _resolve(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(info[4][0] for info in infos))


def signature(secret: str, timestamp: str, body: bytes) -> str:
    """sha256=HMAC(secret, "<timestamp>.<body>") — documented in docs/feed.md."""
    return "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


class HttpWebhookSender(WebhookSenderPort):
    """POSTs events to users' webhooks: fixed body, signed, no redirects, short timeout,
    response body never read. Connects to the address netguard approved."""

    def __init__(self, resolver: Resolver = _resolve, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._resolve = resolver
        self._transport = transport
        self._allowed = allow_list(settings.feed_webhook_allow_hosts)

    async def _address(self, url: str) -> tuple[Target, str]:
        target = parse_target(url, self._allowed)
        try:
            addresses = await self._resolve(target.host, target.port)
        except OSError as exc:
            raise UnsafeTarget("the host name doesn't resolve") from exc
        return target, pick_address(target, addresses)

    async def check(self, url: str) -> str | None:
        try:
            await self._address(url)
        except UnsafeTarget as exc:
            return str(exc)
        return None

    async def deliver(self, url: str, secret: str, body: bytes, event_type: str) -> DeliveryResult:
        try:
            target, address = await self._address(url)
        except UnsafeTarget as exc:
            return DeliveryResult(ok=False, detail=str(exc))
        timestamp = str(int(time.time() * 1000))
        host = f"[{address}]" if ":" in address else address
        headers = {
            "Host": target.host_header,
            "Content-Type": "application/json",
            "User-Agent": "DriveLyrics-Feed/1",
            "X-DriveLyrics-Event": event_type,
            "X-DriveLyrics-Timestamp": timestamp,
            "X-DriveLyrics-Signature": signature(secret, timestamp, body),
        }
        # TLS is verified against the host name, not the address connected to.
        extensions = {"sni_hostname": target.host} if target.scheme == "https" else {}
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=False, transport=self._transport) as client:
                async with client.stream(
                    "POST", f"{target.scheme}://{host}:{target.port}{target.path}", content=body, headers=headers, extensions=extensions
                ) as response:
                    status = response.status_code
        except httpx.HTTPError as exc:
            return DeliveryResult(ok=False, detail=type(exc).__name__)
        return DeliveryResult(ok=200 <= status < 300, detail=f"HTTP {status}")
