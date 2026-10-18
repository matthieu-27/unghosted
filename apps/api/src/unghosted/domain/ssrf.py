"""SSRF policy for link-analysis fetches (user story 3, item 2).

Pure verdicts, no IO: the fetch gateway resolves the host and asks this
module whether every resolved address may be connected to. Blocking is the
default for anything not clearly public.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_ALLOWED_PORTS = frozenset({80, 443})

# Shared-address space (RFC 6598) is "private" for our purposes but the
# ipaddress module classifies it as global.
_CGNAT = ipaddress.ip_network("100.64.0.0/10")
# documentation ranges are also classified global on some Python versions
_DOC_V4 = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
)
_DOC_V6 = ipaddress.ip_network("2001:db8::/32")


class FetchBlockedError(ValueError):
    """The URL or one of its addresses fails the fetch policy."""


@dataclass(frozen=True)
class UrlPolicy:
    """A URL that passed the static checks (scheme, host, port)."""

    scheme: str
    host: str
    port: int


def check_url(raw: str) -> UrlPolicy:
    """Validate scheme, host and port. Only http/https on default ports.

    The host is kept as written: DNS resolution happens in the fetch
    gateway, right before the connection (no TOCTOU window here).
    """
    split = urlsplit(raw.strip())
    if split.scheme.lower() not in _ALLOWED_SCHEMES:
        raise FetchBlockedError(
            f"scheme {split.scheme!r} not allowed (http/https only)"
        )
    if not split.hostname:
        raise FetchBlockedError("URL has no host")
    port = split.port
    if port is not None and port not in _ALLOWED_PORTS:
        raise FetchBlockedError(f"port {port} not allowed (80/443 only)")
    return UrlPolicy(
        scheme=split.scheme.lower(),
        host=split.hostname,
        port=port
        if port is not None
        else 443
        if split.scheme.lower() == "https"
        else 80,
    )


def ip_forbidden(raw: str) -> bool:
    """Whether one resolved address must never be connected to.

    Literal IPs in URLs are checked here too (check_url hands the host to
    ip_forbidden when it parses as an address). IPv4-mapped IPv6 addresses
    are unwrapped first so ::ffff:10.0.0.1 cannot bypass the v4 rules.
    """
    address = ipaddress.ip_address(raw)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    ):
        return True
    if address.version == 4:
        return address in _CGNAT or any(address in net for net in _DOC_V4)
    return address in _DOC_V6


def host_forbidden(host: str) -> bool:
    """Policy check for a host that is already a literal IP address."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip_forbidden(host)


def resolved_ips_forbidden(ips: list[str]) -> list[str]:
    """The subset of resolved addresses that fail policy (empty = allowed)."""
    return [ip for ip in ips if ip_forbidden(ip)]
