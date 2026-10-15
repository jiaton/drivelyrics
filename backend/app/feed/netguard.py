"""Where a webhook may be sent. A user-supplied URL is a way to make this server send
requests into networks it can reach and the user can't (the home LAN, a cloud metadata
endpoint) — so only HTTPS to public addresses, unless the operator allow-lists a host
(FEED_WEBHOOK_ALLOW_HOSTS, e.g. a self-hoster's Home Assistant on the LAN, where plain
HTTP is accepted too). Pure: resolving the name is the adapter's job, which then
connects to the very address checked here, so the name can't be re-pointed between
the check and the request."""

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit


class UnsafeTarget(ValueError):
    pass


@dataclass(frozen=True)
class Target:
    scheme: str
    host: str  # as written in the URL, lowercased, without brackets
    port: int
    path: str  # path + query
    allowlisted: bool

    @property
    def host_header(self) -> str:
        default = 443 if self.scheme == "https" else 80
        host = f"[{self.host}]" if ":" in self.host else self.host
        return host if self.port == default else f"{host}:{self.port}"


def allow_list(raw: str) -> frozenset[str]:
    return frozenset(h.strip().lower().strip("[]") for h in raw.split(",") if h.strip())


def parse_target(url: str, allowed: frozenset[str]) -> Target:
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as exc:
        raise UnsafeTarget("not a valid URL") from exc
    host = (parts.hostname or "").lower()
    if not host:
        raise UnsafeTarget("the URL has no host")
    if parts.username or parts.password:
        raise UnsafeTarget("credentials in the URL aren't allowed")
    allowlisted = host in allowed
    if parts.scheme != "https" and not (allowlisted and parts.scheme == "http"):
        raise UnsafeTarget("the webhook must be an https:// URL")
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return Target(parts.scheme, host, port or (443 if parts.scheme == "https" else 80), path, allowlisted)


def is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    # is_global excludes private, loopback, link-local (cloud metadata), shared/CGNAT,
    # reserved and unspecified ranges.
    return ip.is_global and not ip.is_multicast


def pick_address(target: Target, addresses: list[str]) -> str:
    """The address to connect to. Every address the name resolves to must be public —
    one private answer among public ones is how rebinding tricks work."""
    if not addresses:
        raise UnsafeTarget("the host name doesn't resolve")
    if target.allowlisted:
        return addresses[0]
    if not all(is_public(a) for a in addresses):
        raise UnsafeTarget("the webhook host must be a public internet address")
    return addresses[0]
