"""Gemeinsame Hilfen für die Tests: gefälschte Probe und Uhren, temporäre Datenbank.

Netzwerk wird in Unit-Tests nie wirklich benutzt (``docs/probes.md``, „Testen“).
Echte Pings an 127.0.0.1 stehen nur in Tests mit dem Marker ``loopback``.
"""

import asyncio
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import override

import pytest
from pydantic import Field

from rootping import platform
from rootping.probes.base import Probe, ProbeResult, ProbeSettings
from rootping.storage import Storage
from rootping.timeutil import utc_now


class FakeSettings(ProbeSettings):
    """Einstellungen der Test-Probe: sehr kurze Runden."""

    interval: float = 0.05
    timeout: float = 0.05
    targets: list[str] = Field(default_factory=lambda: ["a", "b"])


class FakeProbe(Probe[FakeSettings]):
    """Probe für Tests: liefert vorgegebene Ergebnisse, kann hängen oder abstürzen.

    Args:
        behaviour: ``"ok"``, ``"crash"`` (Ausnahme) oder ``"hang"`` (antwortet nie).
    """

    name = "fake"

    def __init__(self, settings: FakeSettings | None = None, behaviour: str = "ok") -> None:
        super().__init__(settings or FakeSettings())
        self.behaviour = behaviour
        self.calls: list[str] = []

    @override
    def targets(self) -> list[str]:
        return list(self.settings.targets)

    @override
    async def measure(self, target: str) -> ProbeResult:
        self.calls.append(target)
        if self.behaviour == "crash":
            raise RuntimeError("absichtlicher Testfehler")
        if self.behaviour == "hang":
            await asyncio.sleep(3600)
        return ProbeResult(self.name, target, utc_now(), ok=True, latency_ms=1.0, loss_pct=0.0)


@pytest.fixture
def storage(tmp_path: Path) -> Iterator[Storage]:
    """Frische, migrierte Datenbank in einem temporären Ordner."""
    with Storage.open(tmp_path / "test.db") as db:
        yield db


@pytest.fixture
def restore_logging() -> Iterator[None]:
    """Stellt die Logging-Handler nach Tests wieder her, die setup_logging() aufrufen."""
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    yield
    for handler in root.handlers:
        if handler not in saved_handlers:
            handler.close()
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


@pytest.fixture
def ping_allowed() -> None:
    """Überspringt einen Test, wenn dieser Rechner keinen Ping ohne Rechte erlaubt.

    In der CI (Umgebungsvariable ``CI``) wird nicht übersprungen, sondern der
    Test schlägt fehl: Dort muss Ping funktionieren.
    """
    problem = platform.ping_permission_problem()
    if problem and not os.environ.get("CI"):
        pytest.skip("Ping ohne Rechte ist hier nicht freigegeben (siehe docs/ping.md)")
