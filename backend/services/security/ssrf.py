# -*- coding: utf-8 -*-

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse


@dataclass(frozen=True)
class SSRFValidationResult:
    allowed: bool
    reason: str | None = None


class SSRFProtectionError(ValueError):
    pass


_DEFAULT_BLOCKED_CIDRS = (
    # RFC1918
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    # loopback
    "127.0.0.0/8",
    "::1/128",
    # link-local
    "169.254.0.0/16",
    "fe80::/10",
    # multicast
    "224.0.0.0/4",
    "ff00::/8",
    # documentation/test
    "192.0.2.0/24",
    "198.51.100.0/24",
    "203.0.113.0/24",
)


def validate_outbound_url(
    url: str,
    *,
    allowed_schemes: Iterable[str] = ("http", "https"),
    allowed_hosts: Iterable[str] | None = None,
    blocked_cidrs: Iterable[str] = _DEFAULT_BLOCKED_CIDRS,
    resolve_dns: bool = True,
) -> SSRFValidationResult:
    parsed = urlparse(url)

    if parsed.scheme not in set(allowed_schemes):
        return SSRFValidationResult(False, "scheme_not_allowed")

    if not parsed.hostname:
        return SSRFValidationResult(False, "missing_hostname")

    hostname = parsed.hostname.lower()

    if hostname in {"localhost"}:
        return SSRFValidationResult(False, "localhost_blocked")

    if allowed_hosts is not None and hostname not in {h.lower() for h in allowed_hosts}:
        return SSRFValidationResult(False, "host_not_allowlisted")

    blocked_networks = [ipaddress.ip_network(cidr) for cidr in blocked_cidrs]

    ip = _maybe_parse_ip(hostname)
    if ip is not None:
        return _validate_ip(ip, blocked_networks)

    if not resolve_dns:
        return SSRFValidationResult(True)

    try:
        addrinfos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return SSRFValidationResult(False, "dns_resolution_failed")

    for family, _, _, _, sockaddr in addrinfos:
        if family == socket.AF_INET:
            ip_str = sockaddr[0]
        elif family == socket.AF_INET6:
            ip_str = sockaddr[0]
        else:
            continue

        ip = ipaddress.ip_address(ip_str)
        result = _validate_ip(ip, blocked_networks)
        if not result.allowed:
            return result

    return SSRFValidationResult(True)


def enforce_outbound_url_allowed(*args, **kwargs) -> None:
    result = validate_outbound_url(*args, **kwargs)
    if not result.allowed:
        raise SSRFProtectionError(result.reason or "blocked")


def _maybe_parse_ip(hostname: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(hostname)
    except ValueError:
        return None


def _validate_ip(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    blocked_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> SSRFValidationResult:
    for network in blocked_networks:
        if ip in network:
            return SSRFValidationResult(False, "ip_blocked")

    if ip.is_loopback:
        return SSRFValidationResult(False, "loopback_blocked")
    if ip.is_link_local:
        return SSRFValidationResult(False, "link_local_blocked")
    if ip.is_multicast:
        return SSRFValidationResult(False, "multicast_blocked")
    if ip.is_private:
        return SSRFValidationResult(False, "private_ip_blocked")

    return SSRFValidationResult(True)
