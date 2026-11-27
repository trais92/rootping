"""Tests für den Linux-Teil: Routing-Tabelle, Tunnel-Erkennung, Rechte-Meldung, Loopback-Ping."""

import sys

import pytest

if sys.platform != "linux":
    pytest.skip("nur unter Linux", allow_module_level=True)
assert sys.platform == "linux"  # sagt Pyright, dass der Rest nur unter Linux gilt

from rootping.platform import linux  # noqa: E402 - erst nach der Plattform-Prüfung importierbar

HEADER = "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"


def test_default_gateway_is_found() -> None:
    text = (
        HEADER
        + "eth0\t00000000\t01B2A8C0\t0003\t0\t0\t100\t00000000\t0\t0\t0\n"
        + "eth0\t00B2A8C0\t00000000\t0001\t0\t0\t100\t00FFFFFF\t0\t0\t0\n"
    )
    assert linux.parse_default_gateways(text) == {"eth0": ("192.168.178.1", 100)}


def test_each_interface_keeps_its_lowest_metric() -> None:
    text = (
        HEADER
        + "wlan0\t00000000\t0100A8C0\t0003\t0\t0\t600\t00000000\t0\t0\t0\n"
        + "eth0\t00000000\t01B2A8C0\t0003\t0\t0\t200\t00000000\t0\t0\t0\n"
        + "eth0\t00000000\t02B2A8C0\t0003\t0\t0\t100\t00000000\t0\t0\t0\n"
    )
    assert linux.parse_default_gateways(text) == {
        "wlan0": ("192.168.0.1", 600),
        "eth0": ("192.168.178.2", 100),
    }


def test_routes_that_are_not_default_routes_are_ignored() -> None:
    text = HEADER + "eth0\t00B2A8C0\t00000000\t0001\t0\t0\t100\t00FFFFFF\t0\t0\t0\n"
    assert linux.parse_default_gateways(text) == {}


def test_inactive_default_route_is_ignored() -> None:
    text = HEADER + "eth0\t00000000\t01B2A8C0\t0002\t0\t0\t100\t00000000\t0\t0\t0\n"
    assert linux.parse_default_gateways(text) == {}


def test_loopback_is_not_a_tunnel() -> None:
    # "lo" hat den ARP-Typ 772 (Loopback), kein Tunnel.
    assert linux.is_tunnel("lo") is False


def test_unknown_interface_is_not_a_tunnel() -> None:
    assert linux.is_tunnel("gibt-es-nicht0") is False


def test_permission_help_explains_the_fix() -> None:
    text = linux._permission_help()
    assert "ping_group_range" in text
    assert "sudo sysctl -w" in text
    assert "/etc/sysctl.d/" in text


def test_current_network_on_this_machine_does_not_crash() -> None:
    ctx = linux.current_network()
    assert ctx is None or ctx.gateway.count(".") == 3


@pytest.mark.loopback
@pytest.mark.usefixtures("ping_allowed")
async def test_real_ping_to_loopback() -> None:
    rtt = await linux.echo("127.0.0.1", timeout=1)
    assert rtt is not None
    assert 0 <= rtt < 100
