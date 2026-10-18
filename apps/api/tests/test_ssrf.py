"""SSRF policy verdicts (user story 7, item 2 — the full suite)."""

from __future__ import annotations

import pytest

from unghosted.domain.ssrf import (
    FetchBlockedError,
    check_url,
    host_forbidden,
    ip_forbidden,
    resolved_ips_forbidden,
)

# --- static URL checks -------------------------------------------------------


def test_scheme_must_be_http_or_https() -> None:
    for url in (
        "ftp://example.com",
        "file:///etc/passwd",
        "gopher://x",
        "javascript:alert(1)",
    ):
        with pytest.raises(FetchBlockedError, match="scheme"):
            check_url(url)


def test_missing_host_rejected() -> None:
    with pytest.raises(FetchBlockedError, match="no host"):
        check_url("http:///path")


def test_non_default_port_rejected() -> None:
    with pytest.raises(FetchBlockedError, match="port"):
        check_url("http://example.com:8080/")
    with pytest.raises(FetchBlockedError, match="port"):
        check_url("https://example.com:8443/")


def test_default_ports_allowed() -> None:
    assert check_url("http://example.com/").port == 80
    assert check_url("https://example.com/").port == 443
    assert check_url("http://example.com:80/").port == 80
    assert check_url("https://example.com:443/").port == 443


# --- IPv4 address verdicts ---------------------------------------------------

FORBIDDEN_V4 = [
    "127.0.0.1",
    "127.8.8.8",  # whole loopback range, not just .1
    "10.0.0.1",
    "10.255.255.255",
    "172.16.0.1",
    "172.31.255.255",
    "192.168.1.1",
    "169.254.169.254",  # cloud metadata
    "169.254.0.1",
    "0.0.0.0",
    "100.64.0.1",  # CGNAT
    "192.0.2.1",  # TEST-NET-1
    "198.51.100.7",  # TEST-NET-2
    "203.0.113.9",  # TEST-NET-3
    "224.0.0.1",  # multicast
    "240.0.0.1",  # reserved
    "255.255.255.255",
]

ALLOWED_V4 = ["93.184.216.34", "1.1.1.1", "172.32.0.1", "172.15.255.254"]


@pytest.mark.parametrize("ip", FORBIDDEN_V4)
def test_forbidden_ipv4(ip: str) -> None:
    assert ip_forbidden(ip) is True


@pytest.mark.parametrize("ip", ALLOWED_V4)
def test_allowed_ipv4(ip: str) -> None:
    assert ip_forbidden(ip) is False


# --- IPv6 address verdicts ---------------------------------------------------

FORBIDDEN_V6 = [
    "::",
    "::1",
    "::ffff:127.0.0.1",  # mapped loopback must not bypass v4 rules
    "::ffff:10.0.0.1",  # mapped private
    "fe80::1",  # link-local
    "fc00::1",  # unique local
    "fd12:3456:789a::1",
    "2001:db8::1",  # documentation
    "ff02::1",  # multicast
]

ALLOWED_V6 = ["2606:4700:4700::1111", "2a01:cb00:62::1"]


@pytest.mark.parametrize("ip", FORBIDDEN_V6)
def test_forbidden_ipv6(ip: str) -> None:
    assert ip_forbidden(ip) is True


@pytest.mark.parametrize("ip", ALLOWED_V6)
def test_allowed_ipv6(ip: str) -> None:
    assert ip_forbidden(ip) is False


# --- literal IP hosts and resolution sets ------------------------------------


def test_literal_ip_host_detected() -> None:
    assert host_forbidden("169.254.169.254") is True
    assert host_forbidden("93.184.216.34") is False
    # names are not verdicts here: resolution happens in the gateway
    assert host_forbidden("example.com") is False


def test_resolved_set_reports_only_forbidden() -> None:
    bad = resolved_ips_forbidden(["93.184.216.34", "10.0.0.5"])
    assert bad == ["10.0.0.5"]
    assert resolved_ips_forbidden(["93.184.216.34", "1.1.1.1"]) == []
