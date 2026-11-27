"""Gemeinsame Schnittstelle für alle Messungen (Probes).

Eine Probe misst nur: Sie bekommt ein Ziel, misst eine Runde und gibt ein
:class:`ProbeResult` zurück. Sie speichert nichts, kennt keine Datenbank und
keine anderen Probes. Takt, Fehlerfang und Speichern übernimmt der Scheduler
(``rootping.scheduler``). Hintergrund: ``docs/probes.md``.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProbeSettings(BaseModel):
    """Einstellungen, die jede Probe hat (Abschnitt ``[probes.<name>]`` der Konfiguration).

    Jede Probe erbt davon und ergänzt eigene Felder. Unbekannte Schlüssel sind
    ein Fehler (``extra="forbid"``), damit Tippfehler beim Start auffallen (ADR-010).

    Attributes:
        enabled: Ob die Probe im Messdienst läuft.
        interval: Sekunden pro Messrunde. Eine Runde ergibt eine Zeile in ``measurements``.
        timeout: Sekunden, die auf eine einzelne Antwort gewartet wird.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    interval: float = Field(default=10, gt=0)
    timeout: float = Field(default=2, gt=0, le=30)


@dataclass(frozen=True)
class ProbeResult:
    """Ergebnis einer Messrunde gegen ein Ziel.

    Entspricht einer Zeile der Tabelle ``measurements`` (``docs/datenmodell.md``).
    Felder, die für eine Messart keinen Sinn ergeben (z. B. Jitter bei DNS), bleiben ``None``.

    Attributes:
        probe: Name der Probe, z. B. ``"ping_internet"``.
        target: Ziel der Messung, z. B. ``"1.1.1.1"``.
        ts: Beginn der Messrunde (UTC, mit Zeitzone).
        ok: Hat die Messung grundsätzlich funktioniert (beim Ping: mindestens eine Antwort)?
        latency_ms: Mittlere Antwortzeit in Millisekunden.
        loss_pct: Paketverlust in Prozent (0 bis 100).
        jitter_ms: Schwankung der Antwortzeit in Millisekunden.
        max_ms: Höchste Antwortzeit der Runde in Millisekunden.
        error: Kurzer, fester Fehlercode, z. B. ``"no_reply"`` oder ``"probe_error"``.
    """

    probe: str
    target: str
    ts: datetime
    ok: bool
    latency_ms: float | None = None
    loss_pct: float | None = None
    jitter_ms: float | None = None
    max_ms: float | None = None
    error: str | None = None


class Probe[S: ProbeSettings](ABC):
    """Basisklasse für eine Messung.

    Unterklassen setzen ``name`` und schreiben :meth:`measure`. Ziele, Intervall
    und Timeout kommen aus den Einstellungen, nie aus dem Code.

    Attributes:
        name: Eindeutiger Name, gleich dem Schlüssel in ``PROBES`` und in der Konfiguration.
        settings: Der geprüfte Konfigurationsabschnitt dieser Probe.
    """

    name: str

    def __init__(self, settings: S) -> None:
        """Übernimmt den geprüften Abschnitt ``[probes.<name>]`` der Konfiguration.

        Args:
            settings: Einstellungen dieser Probe.
        """
        self.settings = settings

    @abstractmethod
    def targets(self) -> list[str]:
        """Gibt die Ziele zurück, die in dieser Runde gemessen werden."""

    @abstractmethod
    async def measure(self, target: str) -> ProbeResult:
        """Misst eine Runde gegen ``target``.

        Darf für „Ziel nicht erreichbar“ keine Ausnahme werfen, sondern gibt
        ``ok=False`` mit passendem ``error`` zurück. Unerwartete Ausnahmen fängt
        der Scheduler ab und speichert sie als ``error="probe_error"``.

        Args:
            target: Das Ziel, z. B. eine IPv4-Adresse.

        Returns:
            Das Ergebnis der Runde.
        """
