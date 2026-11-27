"""Tests für die DNS-Messung: echte Abfragen an einen kleinen Test-Server auf 127.0.0.1.

Der Test-Server antwortet je nach Einstellung normal, mit NXDOMAIN, mit
SERVFAIL oder gar nicht. So werden alle Fehlerarten ohne Internet geprüft.
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

import dns.message
import dns.rcode
import dns.rrset
import pytest
from pydantic import ValidationError

from rootping.net import dns_query
from rootping.net.dns_query import DnsQueryError
from rootping.platform import NetworkContext
from rootping.probes.dns import GATEWAY, SYSTEM, DnsProbe, DnsSettings


@dataclass
class FakeDnsServer:
    """Kleiner UDP-DNS-Server für Tests. ``mode``: ok, nxdomain, servfail, silent."""

    mode: str = "ok"
    port: int = 0


class _Protocol(asyncio.DatagramProtocol):
    def __init__(self, server: FakeDnsServer) -> None:
        self.server = server
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        assert isinstance(transport, asyncio.DatagramTransport)
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if self.server.mode == "silent" or self.transport is None:
            return
        request = dns.message.from_wire(data)
        response = dns.message.make_response(request)
        if self.server.mode == "nxdomain":
            response.set_rcode(dns.rcode.NXDOMAIN)
        elif self.server.mode == "servfail":
            response.set_rcode(dns.rcode.SERVFAIL)
        else:
            name = request.question[0].name
            response.answer.append(dns.rrset.from_text(name, 60, "IN", "A", "192.0.2.10"))
        self.transport.sendto(response.to_wire(), addr)


@pytest.fixture
async def fake_dns() -> AsyncIterator[FakeDnsServer]:
    server = FakeDnsServer()
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: _Protocol(server), local_addr=("127.0.0.1", 0)
    )
    server.port = transport.get_extra_info("sockname")[1]
    yield server
    transport.close()


# --- Einzelne Abfrage ------------------------------------------------------------


async def test_successful_query_returns_latency(fake_dns: FakeDnsServer) -> None:
    latency = await dns_query.query("127.0.0.1", "example.com", 2, port=fake_dns.port)
    assert 0 <= latency < 1000


@pytest.mark.parametrize(("mode", "code"), [("nxdomain", "nxdomain"), ("servfail", "servfail")])
async def test_server_errors_have_fixed_codes(
    fake_dns: FakeDnsServer, mode: str, code: str
) -> None:
    fake_dns.mode = mode
    with pytest.raises(DnsQueryError) as info:
        await dns_query.query("127.0.0.1", "example.com", 2, port=fake_dns.port)
    assert info.value.code == code


async def test_silent_server_is_a_timeout(fake_dns: FakeDnsServer) -> None:
    fake_dns.mode = "silent"
    loop = asyncio.get_running_loop()
    start = loop.time()
    with pytest.raises(DnsQueryError) as info:
        await dns_query.query("127.0.0.1", "example.com", 0.3, port=fake_dns.port)
    assert info.value.code == "timeout"
    assert loop.time() - start < 1.5


async def test_server_must_be_an_address() -> None:
    with pytest.raises(ValueError, match=r"dns\.example"):
        await dns_query.query("dns.example", "example.com", 1)


# --- Probe ---------------------------------------------------------------------------


def fake_query(answers: dict[str, float | str]):
    """Gefälschte Abfrage: Zahl = Antwortzeit, Text = Fehlerart."""

    async def query(server: str, name: str, timeout: float) -> float:
        answer = answers[server]
        if isinstance(answer, str):
            raise DnsQueryError(answer)
        return answer

    return query


def make_probe(**kwargs) -> DnsProbe:
    defaults = {
        "route": lambda: NetworkContext("192.168.178.1", "eth0"),
        "system_nameserver": lambda: "127.0.0.53",
    }
    defaults.update(kwargs)
    settings = defaults.pop("settings", DnsSettings())
    return DnsProbe(settings, **defaults)  # pyright: ignore[reportArgumentType]


def test_defaults_match_docs() -> None:
    s = DnsSettings()
    assert (s.targets, s.query, s.interval, s.timeout) == (
        [GATEWAY, SYSTEM, "1.1.1.1"],
        "example.com",
        30,
        3,
    )


def test_hostname_is_not_a_valid_dns_target() -> None:
    with pytest.raises(ValidationError, match="weder 'gateway'"):
        DnsSettings(targets=["dns.google"])


def test_placeholders_become_addresses() -> None:
    assert make_probe().targets() == ["192.168.178.1", "127.0.0.53", "1.1.1.1"]


def test_same_address_is_measured_once() -> None:
    probe = make_probe(system_nameserver=lambda: "192.168.178.1")
    assert probe.targets() == ["192.168.178.1", "1.1.1.1"]


async def test_unresolvable_placeholders_are_reported() -> None:
    probe = make_probe(route=lambda: None, system_nameserver=lambda: None)
    targets = probe.targets()
    assert targets == [GATEWAY, SYSTEM, "1.1.1.1"]
    results = [await probe.measure(t) for t in targets[:2]]
    assert [r.error for r in results] == ["no_gateway", "no_system_dns"]


async def test_measure_success_and_error() -> None:
    probe = make_probe(query=fake_query({"1.1.1.1": 12.5, "192.168.178.1": "timeout"}))
    ok = await probe.measure("1.1.1.1")
    bad = await probe.measure("192.168.178.1")
    assert (ok.ok, ok.latency_ms, ok.loss_pct, ok.error) == (True, 12.5, None, None)
    assert (bad.ok, bad.latency_ms, bad.error) == (False, None, "timeout")
