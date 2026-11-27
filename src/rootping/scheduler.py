"""Der Messdienst: startet die Probes im Takt und gibt die Ergebnisse an ``storage``.

Alles, was die Probes gemeinsam brauchen, passiert hier an einer Stelle,
damit die Probes selbst klein bleiben (``docs/probes.md``, „Was der Scheduler
übernimmt“, und ``docs/messdienst.md``):

1. **Takt:** Jede Probe hat eine eigene Schleife. Runde Nummer ``n`` startet
   ``n * interval`` Sekunden nach dem Start, gemessen mit ``loop.time()``.
   Dadurch läuft der Takt nicht auseinander, auch wenn eine Runde länger
   dauert als das Intervall (beim Ping: 10 Echos plus Timeout des letzten).
   Runden dürfen sich deshalb kurz überlappen.
2. **Sicherheitsnetz:** Hängt eine Messung zu lange oder wirft sie eine
   Ausnahme, wird daraus ein Ergebnis mit ``error="probe_error"``. Eine
   kaputte Probe stoppt nie die anderen.
3. **Messlücken:** Ein Wächter vergleicht jede Sekunde die Wanduhr. Springt sie
   weiter als ``gap_seconds`` (z. B. nach dem Ruhezustand), wird ein Ereignis
   ``gap`` gespeichert. Verpasste Runden werden übersprungen, nicht nachgeholt.
4. **Netzwerk-Kontext:** Vor jeder Runde werden Router und VPN erkannt. Hat
   sich etwas geändert, wird ein Ereignis ``network_change`` gespeichert.
5. **Speichern:** Nur der Scheduler ruft ``storage`` auf. Weil alles in einem
   asyncio-Event-Loop läuft, gibt es nie zwei Schreibzugriffe gleichzeitig.
"""

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from typing import Any

from rootping import platform
from rootping.platform import NetworkContext
from rootping.probes.base import Probe, ProbeResult
from rootping.storage import EventType, Storage
from rootping.timeutil import utc_now

log = logging.getLogger(__name__)

type ResultCallback = Callable[[Sequence[ProbeResult]], None]
"""Wird nach jeder gespeicherten Runde aufgerufen, z. B. für die Ausgabe in der Konsole."""

CLOCK_CHECK_PERIOD_S = 1.0
"""Wie oft der Wächter die Wanduhr prüft (Sekunden)."""

_NOT_CHECKED = object()
"""Markiert, dass der Netzwerk-Kontext noch nie geprüft wurde (kein Ereignis beim Start)."""


class Scheduler:
    """Führt die übergebenen Probes im Takt aus und speichert jede Runde."""

    def __init__(
        self,
        probes: Sequence[Probe[Any]],
        storage: Storage,
        *,
        gap_seconds: float,
        route: Callable[[], NetworkContext | None] | None = None,
        wall_clock: Callable[[], float] = time.time,
        on_results: ResultCallback | None = None,
    ) -> None:
        """Bereitet den Messdienst vor; gestartet wird er mit :meth:`run`.

        Args:
            probes: Die aktivierten Probes.
            storage: Geöffnete Datenbank; der Scheduler ist ihr einziger Schreiber.
            gap_seconds: Ab diesem Sprung der Wanduhr (Sekunden) gilt eine Pause als Messlücke.
            route: Funktion, die den aktuellen Router erkennt; Standard
                :func:`rootping.platform.current_network`. Nur Tests ändern sie.
            wall_clock: Wanduhr in Sekunden; nur Tests ändern sie.
            on_results: Optionaler Aufruf nach jeder gespeicherten Runde.
        """
        self._probes = list(probes)
        self._storage = storage
        self._gap_seconds = gap_seconds
        self._route = route or platform.current_network
        self._wall_clock = wall_clock
        self._on_results = on_results
        self._context: object = _NOT_CHECKED
        self._context_id: int | None = None

    async def run(self, rounds: int | None = None) -> None:
        """Startet alle Probes und läuft, bis er abgebrochen wird (Strg+C).

        Args:
            rounds: Nur für Tests und ``rootping run --rounds``: Nach so vielen
                Runden pro Probe endet der Dienst. ``None`` = endlos.
        """
        clock_watch = asyncio.create_task(self._watch_clock(), name="uhr-waechter")
        try:
            async with asyncio.TaskGroup() as group:
                for probe in self._probes:
                    group.create_task(self._probe_loop(probe, rounds), name=probe.name)
        finally:
            clock_watch.cancel()

    async def _probe_loop(self, probe: Probe[Any], rounds: int | None) -> None:
        """Startet die Runden einer Probe im festen Takt."""
        loop = asyncio.get_running_loop()
        interval = probe.settings.interval
        next_tick = loop.time()
        started = 0
        async with asyncio.TaskGroup() as round_tasks:
            while rounds is None or started < rounds:
                round_tasks.create_task(self.run_round(probe))
                started += 1
                if rounds is not None and started >= rounds:
                    break
                next_tick += interval
                behind = loop.time() - next_tick
                if behind > 0:
                    # Zu spät dran (z. B. Ruhezustand): verpasste Runden überspringen.
                    skipped = int(behind // interval) + 1
                    log.info("%s: %d Runde(n) übersprungen", probe.name, skipped)
                    next_tick += skipped * interval
                await asyncio.sleep(next_tick - loop.time())

    async def run_round(self, probe: Probe[Any]) -> list[ProbeResult]:
        """Misst eine Runde einer Probe (alle Ziele gleichzeitig) und speichert sie.

        Args:
            probe: Die Probe.

        Returns:
            Die gespeicherten Ergebnisse, eines pro Ziel.
        """
        context_id = self._refresh_context()
        try:
            targets = probe.targets()
        except Exception:
            log.exception("%s: Ziele konnten nicht ermittelt werden", probe.name)
            targets = []
        if targets:
            async with asyncio.TaskGroup() as group:
                tasks = [group.create_task(self._measure_safely(probe, t)) for t in targets]
            results = [task.result() for task in tasks]
        else:
            results = [ProbeResult(probe.name, "-", utc_now(), ok=False, error="probe_error")]
        self._storage.save_measurements(results, context_id)
        if self._on_results is not None:
            self._on_results(results)
        return results

    async def _measure_safely(self, probe: Probe[Any], target: str) -> ProbeResult:
        """Ruft ``probe.measure`` auf und macht aus jedem Fehler ein Ergebnis.

        Obergrenze für eine Runde ist ``interval + 2 * timeout``: ein
        ``timeout`` für eine mögliche Namensauflösung vorab (Ping-Ziele als
        Hostname, ADR-011), danach ist auch das letzte Echo sicher beantwortet
        oder verloren.
        """
        ts = utc_now()
        limit = probe.settings.interval + 2 * probe.settings.timeout
        try:
            async with asyncio.timeout(limit):
                return await probe.measure(target)
        except TimeoutError:
            log.error("%s → %s: keine Antwort der Probe nach %.0f s", probe.name, target, limit)
        except Exception:
            log.exception("%s → %s: unerwarteter Fehler", probe.name, target)
        return ProbeResult(probe.name, target, ts, ok=False, error="probe_error")

    def _refresh_context(self) -> int | None:
        """Erkennt den Router und speichert bei einer Änderung ein ``network_change``.

        Returns:
            Die ID des aktuellen Netzwerk-Kontexts oder ``None`` ohne Netz.
        """
        try:
            context = self._route()
        except Exception:
            log.exception("Router-Erkennung fehlgeschlagen")
            context = None
        if context == self._context:
            return self._context_id

        now = utc_now()
        new_id = self._storage.context_id_for(context, now) if context else None
        if self._context is not _NOT_CHECKED:
            old = self._context if isinstance(self._context, NetworkContext) else None
            self._storage.add_event(
                EventType.NETWORK_CHANGE,
                now,
                new_id,
                {"from": _describe(old), "to": _describe(context)},
            )
            log.warning("Netzwechsel: %s → %s", _describe(old), _describe(context))
        self._context, self._context_id = context, new_id
        return new_id

    async def _watch_clock(self) -> None:
        """Speichert ein ``gap``-Ereignis, wenn die Wanduhr ungewöhnlich weit springt.

        Die Wanduhr (``time.time``) läuft im Ruhezustand weiter, der Takt von
        asyncio unter Linux nicht. Der Unterschied verrät die Pause
        (``docs/tech-stack.md`` Abschnitt 3.7).
        """
        last = self._wall_clock()
        while True:
            await asyncio.sleep(CLOCK_CHECK_PERIOD_S)
            now = self._wall_clock()
            if now - last > self._gap_seconds:
                gap = round(now - last, 1)
                log.warning("Messlücke von %.0f s erkannt (Ruhezustand?)", gap)
                self._storage.add_event(
                    EventType.GAP, utc_now(), self._context_id, {"gap_seconds": gap}
                )
            last = now


def _describe(context: NetworkContext | None) -> dict[str, str] | None:
    """Wandelt einen Kontext in ein JSON-taugliches Dictionary für Ereignisse um."""
    if context is None:
        return None
    return {"gateway": context.gateway, "interface": context.interface, "vpn": context.vpn}
