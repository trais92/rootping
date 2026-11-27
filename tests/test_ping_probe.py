"""Tests für die Ping-Probes und ihre Einstellungen, ohne echtes Netzwerk."""

import asyncio
from itertools import pairwise

import pytest
from pydantic import ValidationError

from rootping.net.resolve import ResolveError
from rootping.platform import NetworkContext
from rootping.probes import ping
from rootping.probes.ping import (
    AUTO,
    PingGatewayProbe,
    PingGatewaySettings,
    PingInternetProbe,
    PingInternetSettings,
    PingSettings,
    fixed_rate_echoes,
)

FAST_PERIOD = 0.02


@pytest.fixture(autouse=True)
def fast_echoes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verkürzt den Echo-Abstand von 1 s auf 20 ms, damit die Tests schnell sind."""
    monkeypatch.setattr(ping, "ECHO_PERIOD_S", FAST_PERIOD)


def scripted_echo(answers: list[float | None]):
    """Gefälschtes echo(): liefert der Reihe nach die vorgegebenen Antworten."""
    remaining = iter(answers)

    async def echo(target: str, timeout: float) -> float | None:
        return next(remaining)

    return echo


# --- Einstellungen -----------------------------------------------------------


def test_defaults_match_docs() -> None:
    s = PingSettings()
    assert s.targets == ["1.1.1.1", "9.9.9.9"]
    assert (s.interval, s.timeout, s.echoes_per_round) == (10, 2, 10)
    assert PingGatewaySettings().targets == [AUTO]


@pytest.mark.parametrize("target", ["example.com", "::1", "300.1.1.1", "auto"])
def test_internet_targets_must_be_ipv4(target: str) -> None:
    with pytest.raises(ValidationError, match="keine IPv4-Adresse"):
        PingSettings(targets=[target])


def test_gateway_accepts_auto_and_ipv4() -> None:
    assert PingGatewaySettings(targets=[AUTO, "192.168.0.1"]).targets == [AUTO, "192.168.0.1"]


@pytest.mark.parametrize("interval", [0.5, 2.5])
def test_interval_must_be_whole_seconds(interval: float) -> None:
    with pytest.raises(ValidationError, match="ganze Zahl"):
        PingSettings(interval=interval)


def test_unknown_key_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PingSettings.model_validate({"intervall": 10})


# --- Fester Takt --------------------------------------------------------------


async def test_fixed_rate_does_not_wait_for_slow_replies() -> None:
    sent_at: list[float] = []
    loop = asyncio.get_running_loop()

    async def slow_echo(target: str, timeout: float) -> float | None:
        sent_at.append(loop.time())
        await asyncio.sleep(timeout)  # jede Antwort dauert so lang wie der Timeout
        return None

    start = loop.time()
    rtts = await fixed_rate_echoes(slow_echo, "x", count=5, period=0.05, timeout=0.2)
    duration = loop.time() - start

    assert rtts == [None] * 5
    # Gesendet zu 0, 50, 100, 150, 200 ms – nicht nacheinander mit je 200 ms Wartezeit.
    gaps = [b - a for a, b in pairwise(sent_at)]
    assert all(0.03 < g < 0.12 for g in gaps), gaps
    assert duration < 0.2 + 5 * 0.2  # deutlich schneller als „nacheinander“ (1,2 s)
    assert duration == pytest.approx(0.4, abs=0.15)


async def test_results_keep_send_order_even_if_replies_arrive_out_of_order() -> None:
    delays = iter([0.1, 0.0, 0.05])

    async def echo(target: str, timeout: float) -> float | None:
        delay = next(delays)
        await asyncio.sleep(delay)
        return delay * 1000

    rtts = await fixed_rate_echoes(echo, "x", count=3, period=0.0, timeout=1)
    assert rtts == [100.0, 0.0, 50.0]


# --- Probes -------------------------------------------------------------------


async def test_internet_probe_summarizes_a_round() -> None:
    probe = PingInternetProbe(
        PingInternetSettings(interval=4), echo=scripted_echo([20.0, 25.0, None, 22.0])
    )
    result = await probe.measure("1.1.1.1")
    assert result.probe == "ping_internet"
    assert result.target == "1.1.1.1"
    assert result.ok is True
    assert result.loss_pct == 25.0
    assert result.max_ms == 25.0
    assert result.jitter_ms == pytest.approx(4.0)
    assert result.error is None
    assert result.ts.tzinfo is not None


async def test_round_without_any_reply_is_not_ok() -> None:
    probe = PingInternetProbe(PingInternetSettings(interval=3), echo=scripted_echo([None] * 3))
    result = await probe.measure("9.9.9.9")
    assert (result.ok, result.loss_pct, result.error) == (False, 100.0, "no_reply")


def test_gateway_probe_resolves_auto() -> None:
    probe = PingGatewayProbe(
        PingGatewaySettings(), route=lambda: NetworkContext("192.168.178.1", "eth0")
    )
    assert probe.targets() == ["192.168.178.1"]


def test_gateway_probe_keeps_fixed_addresses() -> None:
    probe = PingGatewayProbe(PingGatewaySettings(targets=["10.0.0.1"]), route=lambda: None)
    assert probe.targets() == ["10.0.0.1"]


async def test_gateway_probe_without_router_reports_no_gateway() -> None:
    probe = PingGatewayProbe(PingGatewaySettings(), route=lambda: None)
    targets = probe.targets()
    assert targets == [AUTO]
    result = await probe.measure(targets[0])
    assert (result.ok, result.error, result.target) == (False, "no_gateway", AUTO)


# --- Hostnamen als Ziel (Opt-in, ADR-011) -------------------------------------------


def test_hostnames_need_opt_in() -> None:
    with pytest.raises(ValidationError, match="allow_hostnames"):
        PingInternetSettings(targets=["www.ea.com"])
    s = PingInternetSettings(targets=["www.ea.com", "1.1.1.1"], allow_hostnames=True)
    assert s.targets == ["www.ea.com", "1.1.1.1"]


@pytest.mark.parametrize("target", ["https://www.ea.com/", "ea", "www.ea.com/fifa", "-a.com"])
def test_urls_and_invalid_names_are_rejected(target: str) -> None:
    with pytest.raises(ValidationError, match="weder eine IPv4-Adresse noch ein Hostname"):
        PingInternetSettings(targets=[target], allow_hostnames=True)


def test_gateway_never_takes_hostnames() -> None:
    with pytest.raises(ValidationError):
        PingGatewaySettings(targets=["fritz.box"])


async def test_hostname_is_resolved_and_stored_by_name() -> None:
    pinged: list[str] = []

    async def echo(target: str, timeout: float) -> float | None:
        pinged.append(target)
        return 30.0

    async def resolver(name: str, timeout: float) -> str:
        return "203.0.113.7"

    settings = PingInternetSettings(interval=2, targets=["www.ea.com"], allow_hostnames=True)
    result = await PingInternetProbe(settings, echo=echo, resolver=resolver).measure("www.ea.com")
    assert pinged == ["203.0.113.7", "203.0.113.7"]
    assert (result.target, result.ok, result.latency_ms) == ("www.ea.com", True, 30.0)


async def test_failed_resolution_is_not_packet_loss() -> None:
    async def resolver(name: str, timeout: float) -> str:
        raise ResolveError("unbekannt")

    settings = PingInternetSettings(interval=2, targets=["www.ea.com"], allow_hostnames=True)
    probe = PingInternetProbe(settings, echo=scripted_echo([]), resolver=resolver)
    result = await probe.measure("www.ea.com")
    assert (result.ok, result.error, result.loss_pct) == (False, "resolve_failed", None)
