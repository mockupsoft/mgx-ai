import socket

import pytest

from backend.services.security.ssrf import validate_outbound_url


def test_ssrf_blocks_localhost() -> None:
    assert validate_outbound_url("http://localhost").allowed is False


def test_ssrf_blocks_private_ip() -> None:
    assert validate_outbound_url("http://10.0.0.1").allowed is False


def test_ssrf_blocks_non_http_scheme() -> None:
    assert validate_outbound_url("file:///etc/passwd").allowed is False


def test_ssrf_blocks_dns_resolving_to_private(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, None, None, None, ("127.0.0.1", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    assert validate_outbound_url("http://example.com").allowed is False
