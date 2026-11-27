"""Tests für den Windows-Teil (laufen nur unter Windows, z. B. in der CI).

Hinweis: GitHub-Windows-Runner laufen als Administrator. Dass der Ping auch
**ohne** Adminrechte geht, beweist erst ``rootping check`` auf einem normalen
Benutzerkonto (``docs/ping.md``).
"""

import sys

import pytest

if sys.platform != "win32":
    pytest.skip("nur unter Windows", allow_module_level=True)
assert sys.platform == "win32"  # sagt Pyright, dass der Rest nur unter Windows gilt

from rootping.platform import windows  # noqa: E402 - erst nach der Plattform-Prüfung importierbar


def test_ipaddr_roundtrip() -> None:
    for address in ["127.0.0.1", "192.168.178.1", "1.2.3.4", "255.255.255.255"]:
        assert windows.from_ipaddr(windows.to_ipaddr(address)) == address


def test_reply_struct_has_expected_size() -> None:
    import ctypes

    # 28 Bytes (32 Bit) bzw. 40 Bytes (64 Bit), wie ICMP_ECHO_REPLY in ipexport.h.
    expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert ctypes.sizeof(windows._IcmpEchoReply) == expected


def test_icmp_api_is_usable() -> None:
    assert windows.ping_permission_problem() is None


@pytest.mark.loopback
async def test_real_ping_to_loopback() -> None:
    rtt = await windows.echo("127.0.0.1", timeout=1)
    assert rtt is not None
    assert 0 <= rtt < 100


async def test_unreachable_documentation_address_is_lost() -> None:
    # 192.0.2.1 ist laut RFC 5737 nur für Dokumentation reserviert und antwortet nie.
    assert await windows.echo("192.0.2.1", timeout=0.5) is None


def test_default_route_does_not_crash() -> None:
    ctx = windows.default_route()
    assert ctx is None or ctx.gateway.count(".") == 3
