"""Ping-Messungen: zum Router (``ping_gateway``) und ins Internet (``ping_internet``).

Eine Runde dauert ``interval`` Sekunden (Standard 10). Darin wird **fest jede
Sekunde** ein Echo gesendet, ohne auf die vorige Antwort zu warten. So bleibt
der Takt auch bei Paketverlust gleich (Befund B2, ADR-006). Aus den Einzelwerten
berechnet :func:`~rootping.probes.summary.summarize` Mittelwert, Maximum,
Verlust und Jitter. Ablauf und Beispiele: ``docs/ping.md``.

Ziele sind normalerweise IPv4-Adressen. Bei ``ping_internet`` lassen sich mit
``allow_hostnames = true`` auch Namen wie ``www.ea.com`` eintragen, um eine
Website oder einen Spieldienst gezielt zu testen. Der Name wird vor jeder
Runde neu übersetzt; klappt das nicht, heißt das Ergebnis ``resolve_failed``
statt Paketverlust (ADR-011).
"""

import asyncio
import ipaddress
import logging
import re
from collections.abc import Callable, Coroutine
from typing import Annotated, Any, override

from pydantic import AfterValidator, Field, model_validator

from rootping import platform
from rootping.net import icmp, resolve
from rootping.probes.base import Probe, ProbeResult, ProbeSettings
from rootping.probes.summary import summarize
from rootping.timeutil import utc_now

log = logging.getLogger(__name__)

ECHO_PERIOD_S = 1.0
"""Abstand zwischen zwei Echos in Sekunden. Fest 1 Echo pro Sekunde, weil die
Schwellen in ``docs/diagnose.md`` darauf beruhen (ADR-006). Eine Runde von
``interval`` Sekunden hat deshalb ``interval`` Echos (siehe ``echoes_per_round``)."""

AUTO = "auto"
"""Platzhalter-Ziel für ``ping_gateway``: Router automatisch erkennen."""

type EchoFunc = Callable[[str, float], Coroutine[Any, Any, float | None]]
"""Signatur von :func:`rootping.net.icmp.echo`; Tests setzen hier eine Fälschung ein."""

type RouteFunc = Callable[[], platform.NetworkContext | None]
"""Signatur von :func:`rootping.platform.current_network`; Tests setzen hier eine Fälschung ein."""

type ResolveFunc = Callable[[str, float], Coroutine[Any, Any, str]]
"""Signatur von :func:`rootping.net.resolve.resolve_ipv4`; Tests setzen hier eine Fälschung ein."""

_HOSTNAME = re.compile(
    r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9]$",
    re.IGNORECASE,
)
"""Hostname mit mindestens einem Punkt, z. B. ``www.ea.com`` (RFC 1123, ohne ``https://``)."""


def is_ipv4(value: str) -> bool:
    """Prüft, ob ``value`` eine IPv4-Adresse ist."""
    try:
        ipaddress.IPv4Address(value)
    except ValueError:
        return False
    return True


def _ipv4(value: str) -> str:
    """Prüft, dass ``value`` eine IPv4-Adresse ist (keine Namen, siehe ADR-011)."""
    try:
        ipaddress.IPv4Address(value)
    except ValueError:
        raise ValueError(
            f"{value!r} ist keine IPv4-Adresse. Ping-Ziele müssen Adressen sein, "
            "keine Namen (ADR-011)."
        ) from None
    return value


def _ipv4_or_auto(value: str) -> str:
    """Wie :func:`_ipv4`, erlaubt zusätzlich ``"auto"`` (Router automatisch erkennen)."""
    return value if value == AUTO else _ipv4(value)


def _ipv4_or_hostname(value: str) -> str:
    """Erlaubt IPv4-Adressen und Hostnamen; ob Namen erlaubt sind, prüft das Modell."""
    if is_ipv4(value) or _HOSTNAME.match(value):
        return value
    raise ValueError(
        f"{value!r} ist weder eine IPv4-Adresse noch ein Hostname. "
        "Bei Websites nur den Namen eintragen, z. B. 'www.ea.com' statt 'https://www.ea.com/'."
    )


class PingSettings(ProbeSettings):
    """Einstellungen einer Ping-Probe.

    Attributes:
        targets: IPv4-Adressen, die gleichzeitig gemessen werden.
        interval: Sekunden pro Runde; ganze Zahl, weil pro Sekunde ein Echo gesendet wird.
        timeout: Sekunden, die auf jede einzelne Antwort gewartet wird.
    """

    targets: list[Annotated[str, AfterValidator(_ipv4)]] = Field(
        default=["1.1.1.1", "9.9.9.9"], min_length=1
    )

    @model_validator(mode="after")
    def _interval_is_whole_seconds(self) -> PingSettings:
        """Stellt sicher, dass eine Runde aus ganzen Sekunden (= Echos) besteht."""
        if self.interval < 1 or self.interval != int(self.interval):
            raise ValueError("interval muss bei Ping eine ganze Zahl ≥ 1 sein (1 Echo/Sekunde).")
        return self

    @property
    def echoes_per_round(self) -> int:
        """Anzahl Echos pro Runde: ein Echo pro Sekunde, bei 10 s Intervall also 10."""
        return int(self.interval)


class PingInternetSettings(PingSettings):
    """Einstellungen von ``ping_internet``.

    Attributes:
        targets: IPv4-Adressen; mit ``allow_hostnames`` auch Hostnamen.
        allow_hostnames: Namen wie ``www.ea.com`` als Ziel erlauben (Standard aus, ADR-011).
    """

    targets: list[Annotated[str, AfterValidator(_ipv4_or_hostname)]] = Field(
        default=["1.1.1.1", "9.9.9.9"], min_length=1
    )
    allow_hostnames: bool = False

    @model_validator(mode="after")
    def _hostnames_need_opt_in(self) -> PingInternetSettings:
        """Lehnt Namen ab, solange ``allow_hostnames`` nicht eingeschaltet ist."""
        names = [t for t in self.targets if not is_ipv4(t)]
        if names and not self.allow_hostnames:
            raise ValueError(
                f"{names[0]!r} ist keine IPv4-Adresse. Namen als Ziel nur mit "
                "allow_hostnames = true (ADR-011, docs/ping.md)."
            )
        return self


class PingGatewaySettings(PingSettings):
    """Einstellungen von ``ping_gateway``. ``"auto"`` erkennt den Router selbst."""

    targets: list[Annotated[str, AfterValidator(_ipv4_or_auto)]] = Field(
        default=[AUTO], min_length=1
    )


async def fixed_rate_echoes(
    echo: EchoFunc, target: str, *, count: int, period: float, timeout: float
) -> list[float | None]:
    """Sendet ``count`` Echos in festem Takt und sammelt die Antworten.

    Echo Nummer ``i`` startet genau ``i * period`` Sekunden nach Beginn,
    egal ob frühere Antworten schon da sind (Echos dürfen sich überlappen).
    Der Takt hängt an ``loop.time()`` und läuft deshalb nicht auseinander.

    Args:
        echo: Funktion, die ein Echo sendet (normalerweise :func:`rootping.net.icmp.echo`).
        target: IPv4-Adresse des Ziels.
        count: Anzahl Echos.
        period: Abstand zwischen zwei Echos in Sekunden.
        timeout: Sekunden, die auf jede Antwort gewartet wird.

    Returns:
        Antwortzeiten in Millisekunden in Sendereihenfolge, ``None`` = verloren.
    """
    loop = asyncio.get_running_loop()
    start = loop.time()
    tasks: list[asyncio.Task[float | None]] = []
    async with asyncio.TaskGroup() as group:
        for i in range(count):
            await asyncio.sleep(max(0.0, start + i * period - loop.time()))
            tasks.append(group.create_task(echo(target, timeout)))
    return [task.result() for task in tasks]


class PingProbe(Probe[PingSettings]):
    """Gemeinsame Logik beider Ping-Probes. Wird selbst nicht registriert."""

    def __init__(
        self,
        settings: PingSettings,
        echo: EchoFunc | None = None,
        resolver: ResolveFunc | None = None,
    ) -> None:
        """Übernimmt die Einstellungen.

        Args:
            settings: Abschnitt ``[probes.<name>]`` der Konfiguration.
            echo: Funktion für ein einzelnes Echo; Standard :func:`rootping.net.icmp.echo`.
                Nur Tests setzen hier etwas anderes ein.
            resolver: Übersetzt Hostnamen; Standard :func:`rootping.net.resolve.resolve_ipv4`.
                Nur Tests setzen hier etwas anderes ein.
        """
        super().__init__(settings)
        self._echo = echo or icmp.echo
        self._resolve = resolver or resolve.resolve_ipv4

    @override
    def targets(self) -> list[str]:
        """Gibt die Ziele aus der Konfiguration zurück."""
        return list(self.settings.targets)

    @override
    async def measure(self, target: str) -> ProbeResult:
        """Misst eine Runde (Standard: 10 Echos in 10 Sekunden) und fasst sie zusammen.

        Ist ``target`` ein Hostname, wird er zuerst übersetzt. Gespeichert wird
        der Name, damit die Messreihe zusammenbleibt, auch wenn die Adresse wechselt.

        Args:
            target: IPv4-Adresse oder (mit ``allow_hostnames``) Hostname des Ziels.

        Returns:
            Das Ergebnis; ``ok`` ist wahr, wenn mindestens eine Antwort kam.
            ``error="resolve_failed"``, wenn der Name nicht übersetzt werden konnte.
        """
        ts = utc_now()
        address = target
        if not is_ipv4(target):
            try:
                address = await self._resolve(target, self.settings.timeout)
            except resolve.ResolveError as err:
                log.warning("%s: %s", self.name, err)
                return ProbeResult(self.name, target, ts, ok=False, error="resolve_failed")
            log.debug("%s: %s → %s", self.name, target, address)
        rtts = await fixed_rate_echoes(
            self._echo,
            address,
            count=self.settings.echoes_per_round,
            period=ECHO_PERIOD_S,
            timeout=self.settings.timeout,
        )
        summary = summarize(rtts)
        return ProbeResult(
            probe=self.name,
            target=target,
            ts=ts,
            ok=summary.received > 0,
            latency_ms=summary.avg_ms,
            loss_pct=summary.loss_pct,
            jitter_ms=summary.jitter_ms,
            max_ms=summary.max_ms,
            error=None if summary.received > 0 else "no_reply",
        )


class PingInternetProbe(PingProbe):
    """Ping zu festen Zielen im Internet (Standard: 1.1.1.1 und 9.9.9.9)."""

    name = "ping_internet"

    def __init__(
        self,
        settings: PingInternetSettings,
        echo: EchoFunc | None = None,
        resolver: ResolveFunc | None = None,
    ) -> None:
        """Übernimmt die Einstellungen.

        Args:
            settings: Abschnitt ``[probes.ping_internet]`` der Konfiguration.
            echo: Funktion für ein einzelnes Echo; nur Tests ändern sie.
            resolver: Übersetzt Hostnamen; nur Tests ändern ihn.
        """
        super().__init__(settings, echo, resolver)


class PingGatewayProbe(PingProbe):
    """Ping zum eigenen Router.

    Steht in der Konfiguration ``targets = ["auto"]``, wird der Router vor jeder
    Runde neu erkannt (Netzwechsel). Im Labor steht dort stattdessen die feste
    Adresse des Router-Containers.
    """

    name = "ping_gateway"

    def __init__(
        self,
        settings: PingGatewaySettings,
        echo: EchoFunc | None = None,
        route: RouteFunc | None = None,
    ) -> None:
        """Übernimmt die Einstellungen.

        Args:
            settings: Abschnitt ``[probes.ping_gateway]`` der Konfiguration.
            echo: Funktion für ein einzelnes Echo; nur Tests ändern sie.
            route: Funktion, die den Router erkennt; Standard
                :func:`rootping.platform.current_network`. Nur Tests ändern sie.
        """
        super().__init__(settings, echo)
        self._route = route or platform.current_network

    @override
    def targets(self) -> list[str]:
        """Gibt die Ziele zurück; ``"auto"`` wird durch die Router-Adresse ersetzt.

        Wird kein Router gefunden (kein Netz), bleibt ``"auto"`` stehen. :meth:`measure`
        speichert dann ein Ergebnis mit ``error="no_gateway"``, damit der Ausfall
        in den Daten sichtbar ist.
        """
        resolved: list[str] = []
        for target in self.settings.targets:
            if target == AUTO:
                context = self._route()
                resolved.append(context.gateway if context else AUTO)
            else:
                resolved.append(target)
        return resolved

    @override
    async def measure(self, target: str) -> ProbeResult:
        """Misst eine Runde zum Router oder meldet ``no_gateway``, wenn keiner erkannt wurde.

        Args:
            target: IPv4-Adresse des Routers oder ``"auto"``, wenn keiner gefunden wurde.

        Returns:
            Das Ergebnis der Runde.
        """
        if target == AUTO:
            return ProbeResult(
                probe=self.name, target=AUTO, ts=utc_now(), ok=False, error="no_gateway"
            )
        return await super().measure(target)
