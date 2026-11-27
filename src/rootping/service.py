"""Baut den Messdienst aus der Konfiguration zusammen und startet ihn.

Bindeglied zwischen CLI und den Bausteinen: Konfiguration → Probes →
Scheduler → Speicherung. Die CLI (``cli.py``) bleibt dadurch dünn, und Tests
können den Dienst ohne Kommandozeile starten.
"""

import logging
from typing import Any

from rootping.config import Settings
from rootping.probes import PROBES, Probe
from rootping.scheduler import ResultCallback, Scheduler
from rootping.storage import Storage

log = logging.getLogger(__name__)


def build_probes(settings: Settings) -> list[Probe[Any]]:
    """Erzeugt alle in der Konfiguration aktivierten Probes.

    Für jeden Eintrag in ``PROBES`` wird der gleichnamige Abschnitt
    ``[probes.<name>]`` gelesen. Ein Test stellt sicher, dass beide Listen
    zusammenpassen.

    Args:
        settings: Geprüfte Konfiguration.

    Returns:
        Die aktivierten Probes in der Reihenfolge von ``PROBES``.
    """
    probes: list[Probe[Any]] = []
    for name, probe_class in PROBES.items():
        probe_settings = getattr(settings.probes, name)
        if probe_settings.enabled:
            probes.append(probe_class(probe_settings))
        else:
            log.info("Probe %s ist in der Konfiguration abgeschaltet", name)
    return probes


async def run_service(
    settings: Settings, *, rounds: int | None = None, on_results: ResultCallback | None = None
) -> None:
    """Öffnet die Datenbank und lässt den Messdienst laufen.

    Args:
        settings: Geprüfte Konfiguration.
        rounds: Runden pro Probe; ``None`` = bis zum Abbruch.
        on_results: Optionaler Aufruf nach jeder gespeicherten Runde.
    """
    probes = build_probes(settings)
    if not probes:
        log.warning("Keine Probe aktiviert, nichts zu tun.")
        return
    with Storage.open(settings.database_path()) as storage:
        scheduler = Scheduler(
            probes, storage, gap_seconds=settings.service.gap_seconds, on_results=on_results
        )
        await scheduler.run(rounds=rounds)
