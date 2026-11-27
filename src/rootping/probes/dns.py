"""DNS-Messung (``dns_lookup``): Wie schnell und wie zuverlässig antworten DNS-Server?

Pro Runde (Standard alle 30 s) wird jeder Server einmal nach einem festen
Namen gefragt (Standard ``example.com``). Ziele:

- ``"gateway"``: der Router selbst (die meisten Heimrouter leiten DNS weiter).
- ``"system"``: der DNS-Server des Betriebssystems.
- IPv4-Adressen, z. B. ``"1.1.1.1"`` als öffentlicher Vergleich.

``gateway`` und ``system`` werden vor jeder Runde in Adressen übersetzt und
als Adresse gespeichert. Ob eine Zeile den Router-DNS betrifft, erkennt man am
Vergleich mit ``network_contexts.gateway``. Zeigen zwei Ziele auf dieselbe
Adresse, wird sie nur einmal gemessen. Hintergrund: ``docs/dns.md``.
"""

import ipaddress
from collections.abc import Callable, Coroutine
from typing import Annotated, Any, override

from pydantic import AfterValidator, Field

from rootping import platform
from rootping.net import dns_query
from rootping.probes.base import Probe, ProbeResult, ProbeSettings
from rootping.timeutil import utc_now

GATEWAY = "gateway"
"""Platzhalter-Ziel: DNS-Anfrage direkt an den Router."""

SYSTEM = "system"
"""Platzhalter-Ziel: DNS-Server des Betriebssystems."""

type QueryFunc = Callable[[str, str, float], Coroutine[Any, Any, float]]
"""Signatur von :func:`rootping.net.dns_query.query`; Tests setzen hier eine Fälschung ein."""


def _dns_target(value: str) -> str:
    """Erlaubt ``"gateway"``, ``"system"`` oder eine IPv4-Adresse."""
    if value in (GATEWAY, SYSTEM):
        return value
    try:
        ipaddress.IPv4Address(value)
    except ValueError:
        raise ValueError(
            f"{value!r} ist weder 'gateway', 'system' noch eine IPv4-Adresse."
        ) from None
    return value


class DnsSettings(ProbeSettings):
    """Einstellungen von ``dns_lookup``.

    Attributes:
        targets: DNS-Server: ``"gateway"``, ``"system"`` oder IPv4-Adressen.
        query: Name, der abgefragt wird (A-Eintrag).
        interval: Sekunden pro Runde.
        timeout: Sekunden bis eine Abfrage als ``timeout`` gilt.
    """

    targets: list[Annotated[str, AfterValidator(_dns_target)]] = Field(
        default=[GATEWAY, SYSTEM, "1.1.1.1"], min_length=1
    )
    query: str = Field(default="example.com", min_length=1)
    interval: float = Field(default=30, gt=0)
    timeout: float = Field(default=3, gt=0, le=30)


class DnsProbe(Probe[DnsSettings]):
    """Misst die Antwortzeit von DNS-Servern und die Art eines Fehlers."""

    name = "dns_lookup"

    def __init__(
        self,
        settings: DnsSettings,
        query: QueryFunc | None = None,
        route: Callable[[], platform.NetworkContext | None] | None = None,
        system_nameserver: Callable[[], str | None] | None = None,
    ) -> None:
        """Übernimmt die Einstellungen.

        Args:
            settings: Abschnitt ``[probes.dns_lookup]`` der Konfiguration.
            query: Funktion für eine Abfrage; Standard :func:`rootping.net.dns_query.query`.
            route: Router-Erkennung; Standard :func:`rootping.platform.default_route`.
            system_nameserver: DNS-Server des Systems; Standard
                :func:`rootping.net.dns_query.system_nameserver`.
        """
        super().__init__(settings)
        self._query = query or dns_query.query
        self._route = route or platform.default_route
        self._system_nameserver = system_nameserver or dns_query.system_nameserver

    @override
    def targets(self) -> list[str]:
        """Übersetzt ``gateway`` und ``system`` in Adressen; doppelte Adressen fallen weg.

        Lässt sich ein Platzhalter nicht übersetzen (kein Router, kein System-DNS),
        bleibt er stehen; :meth:`measure` meldet dann einen Fehler.
        """
        resolved: list[str] = []
        for target in self.settings.targets:
            address: str | None = target
            if target == GATEWAY:
                context = self._route()
                address = context.gateway if context else None
            elif target == SYSTEM:
                address = self._system_nameserver()
            entry = address or target
            if entry not in resolved:
                resolved.append(entry)
        return resolved

    @override
    async def measure(self, target: str) -> ProbeResult:
        """Stellt eine Abfrage an ``target`` und gibt Antwortzeit oder Fehlerart zurück.

        Args:
            target: IPv4-Adresse des Servers, oder ``"gateway"``/``"system"``,
                wenn der Platzhalter nicht übersetzt werden konnte.

        Returns:
            Das Ergebnis; ``loss_pct``, ``jitter_ms`` und ``max_ms`` bleiben leer.
        """
        ts = utc_now()
        if target == GATEWAY:
            return ProbeResult(self.name, target, ts, ok=False, error="no_gateway")
        if target == SYSTEM:
            return ProbeResult(self.name, target, ts, ok=False, error="no_system_dns")
        try:
            latency = await self._query(target, self.settings.query, self.settings.timeout)
        except dns_query.DnsQueryError as err:
            return ProbeResult(self.name, target, ts, ok=False, error=err.code)
        return ProbeResult(self.name, target, ts, ok=True, latency_ms=latency)
