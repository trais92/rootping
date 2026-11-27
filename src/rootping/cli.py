"""Kommandozeile von RootPing (Typer).

Befehle in Sprint 1:

- ``rootping run``: Messdienst starten (läuft bis Strg+C).
- ``rootping check``: Umgebung prüfen: Konfiguration, Ping-Rechte, Router und
  ein kurzer Test-Ping. Gedacht als erster Schritt auf einem neuen Rechner,
  z. B. für den Windows-Test ohne Adminrechte (``docs/ping.md``).

Die CLI enthält keine Logik, sie ruft nur ``config``, ``service`` und
``platform`` auf. Ausgaben an den Menschen gehen über ``typer.echo``.
"""

import asyncio
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer

from rootping import __version__, platform
from rootping.config import ConfigError, Settings, default_config_path, load_settings
from rootping.logsetup import setup_logging
from rootping.net import icmp
from rootping.probes.base import ProbeResult
from rootping.probes.ping import ECHO_PERIOD_S, fixed_rate_echoes
from rootping.service import run_service

app = typer.Typer(
    help="RootPing: misst Ping zum Router und ins Internet und speichert alles in SQLite.",
    no_args_is_help=True,
    add_completion=False,
)

log = logging.getLogger(__name__)

ConfigOption = Annotated[
    Path | None,
    typer.Option("--config", "-c", help="Konfigurationsdatei (TOML). Standard: siehe 'check'."),
]

CHECK_ECHOES = 3
"""Anzahl Test-Echos pro Ziel bei ``rootping check``."""


def _load(config: Path | None) -> Settings:
    """Lädt die Konfiguration oder beendet mit einer verständlichen Meldung (Exit-Code 2)."""
    try:
        return load_settings(config)
    except ConfigError as err:
        typer.echo(f"Fehler in der Konfiguration:\n{err}", err=True)
        raise typer.Exit(code=2) from err


def _format_result(result: ProbeResult) -> str:
    """Formatiert ein Ergebnis als eine lesbare Zeile für die Konsole."""

    def ms(value: float | None) -> str:
        return "–" if value is None else f"{value:.1f} ms"

    if not result.ok:
        return f"{result.probe:<14} {result.target:<15} FEHLER: {result.error}"
    return (
        f"{result.probe:<14} {result.target:<15} "
        f"ø {ms(result.latency_ms):>9}  max {ms(result.max_ms):>9}  "
        f"Verlust {result.loss_pct or 0:>5.1f} %  Jitter {ms(result.jitter_ms):>9}"
    )


def _print_results(results: Sequence[ProbeResult]) -> None:
    """Gibt die Ergebnisse einer Runde in der Konsole aus."""
    for result in results:
        typer.echo(_format_result(result))


@app.command()
def run(
    config: ConfigOption = None,
    rounds: Annotated[
        int | None,
        typer.Option(min=1, help="Nach so vielen Runden pro Messung beenden (Standard: endlos)."),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Mehr Details.")] = False,
) -> None:
    """Startet den Messdienst. Beenden mit Strg+C."""
    settings = _load(config)
    log_file = setup_logging("run", verbose=verbose)
    problem = platform.ping_permission_problem()
    if problem:
        typer.echo(problem, err=True)
        raise typer.Exit(code=3)

    typer.echo(f"RootPing {__version__} – Datenbank: {settings.database_path()}")
    typer.echo(f"Log-Datei: {log_file}. Beenden mit Strg+C.")
    try:
        asyncio.run(run_service(settings, rounds=rounds, on_results=_print_results))
    except KeyboardInterrupt:
        typer.echo("Beendet.")


@app.command()
def check(config: ConfigOption = None) -> None:
    """Prüft Konfiguration, Ping-Rechte und Router und sendet ein paar Test-Pings."""
    settings = _load(config)
    config_path = config or default_config_path()
    source = config_path if config_path.is_file() else f"{config_path} (nicht vorhanden)"
    typer.echo(f"RootPing {__version__}")
    typer.echo(f"Konfiguration: {source}")
    typer.echo(f"Datenbank:     {settings.database_path()}")

    problem = platform.ping_permission_problem()
    if problem:
        typer.echo(f"\nPing-Rechte:   FEHLT\n{problem}", err=True)
        raise typer.Exit(code=3)
    typer.echo("Ping-Rechte:   OK (ohne Admin/root)")

    context = platform.default_route()
    if context is None:
        typer.echo("Router:        nicht gefunden (keine Standardroute, kein Netz?)")
    else:
        typer.echo(f"Router:        {context.gateway} über {context.interface}")

    targets = [context.gateway] if context else []
    targets += settings.probes.ping_internet.targets[:1]
    if not targets:
        return
    typer.echo(f"\nTest-Ping, je {CHECK_ECHOES} Echos:")
    for target in targets:
        rtts = asyncio.run(
            fixed_rate_echoes(
                icmp.echo,
                target,
                count=CHECK_ECHOES,
                period=ECHO_PERIOD_S,
                timeout=settings.probes.ping_internet.timeout,
            )
        )
        shown = ", ".join("verloren" if rtt is None else f"{rtt:.1f} ms" for rtt in rtts)
        typer.echo(f"  {target:<15} {shown}")


@app.callback()
def main() -> None:
    """RootPing – Netzwerk-Diagnose mit Messwerten statt Raten."""
