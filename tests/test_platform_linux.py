"""Tests für den Linux-Teil: Routing-Tabelle lesen, Rechte-Meldung, echter Loopback-Ping."""

import sys

import pytest

if sys.platform != "linux":
    pytest.skip("nur unter Linux", allow_module_level=True)
assert sys.platform == "linux"  # sagt Pyright, dass der Rest nur unter Linux gilt

from rootping.platform import linux  # noqa: E402 - erst nach der Plattform-Prüfung importierbar

HEADER = "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"


def test_default_route_is_found() -> None:
    text = (
        HEADER
        + "eth0\t00000000\t01B2A8C0\t0003\t0\t0\t100\t00000000\t0\t0\t0\n"
        + "eth0\t00B2A8C0\t00000000\t0001\t0\t0\t100\t00FFFFFF\t0\t0\t0\n"
    )
    ctx = linux.parse_proc_net_route(text)
    assert ctx is not None
    assert (ctx.gateway, ctx.interface) == ("192.168.178.1", "eth0")


def test_lowest_metric_wins() -> None:
    text = (
        HEADER
        + "wlan0\t00000000\t0100A8C0\t0003\t0\t0\t600\t00000000\t0\t0\t0\n"
        + "eth0\t00000000\t01B2A8C0\t0003\t0\t0\t100\t00000000\t0\t0\t0\n"
    )
    ctx = linux.parse_proc_net_route(text)
    assert ctx is not None
    assert ctx.interface == "eth0"


def test_no_default_route_means_no_network() -> None:
    text = HEADER + "eth0\t00B2A8C0\t00000000\t0001\t0\t0\t100\t00FFFFFF\t0\t0\t0\n"
    assert linux.parse_proc_net_route(text) is None


def test_inactive_default_route_is_ignored() -> None:
    text = HEADER + "eth0\t00000000\t01B2A8C0\t0002\t0\t0\t100\t00000000\t0\t0\t0\n"
    assert linux.parse_proc_net_route(text) is None


def test_permission_help_explains_the_fix() -> None:
    text = linux._permission_help()
    assert "ping_group_range" in text
    assert "sudo sysctl -w" in text
    assert "/etc/sysctl.d/" in text


def test_default_route_on_this_machine_does_not_crash() -> None:
    ctx = linux.default_route()
    assert ctx is None or ctx.gateway.count(".") == 3


@pytest.mark.loopback
@pytest.mark.usefixtures("ping_allowed")
async def test_real_ping_to_loopback() -> None:
    rtt = await linux.echo("127.0.0.1", timeout=1)
    assert rtt is not None
    assert 0 <= rtt < 100
