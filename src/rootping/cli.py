"""Kommandozeile von RootPing (Typer).

Befehle in Sprint 1:

- ``rootping run``: Messdienst starten (läuft bis Strg+C).
- ``rootping check``: Umgebung prüfen: Konfiguration, Ping-Rechte, Router,
  ein paar Test-Pings und je eine DNS-Abfrage. Gedacht als erster Schritt auf einem neuen Rechner,
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
from rootping.probes.dns import DnsProbe
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

    head = f"{result.probe:<14} {result.target:<15}"
    if not result.ok:
        return f"{head} FEHLER: {result.error}"
    parts = [f"ø {ms(result.latency_ms):>9}"]
    # Nur Werte zeigen, die es für diese Messart gibt (DNS hat z. B. keinen Verlust).
    if result.max_ms is not None:
        parts.append(f"max {ms(result.max_ms):>9}")
    if result.loss_pct is not None:
        parts.append(f"Verlust {result.loss_pct:>5.1f} %")
    if result.jitter_ms is not None:
        parts.append(f"Jitter {ms(result.jitter_ms):>9}")
    return f"{head} {'  '.join(parts)}"


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
    """Prüft Konfiguration, Ping-Rechte und Router und testet Ping und DNS."""
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

    asyncio.run(_test_network(settings, context))


async def _test_network(settings: Settings, context: platform.NetworkContext | None) -> None:
    """Sendet für ``check`` ein paar Test-Pings und je eine DNS-Abfrage und zeigt das Ergebnis."""
    ping_settings = settings.probes.ping_internet
    targets = [context.gateway] if context else []
    targets += ping_settings.targets[:1]
    typer.echo(f"\nTest-Ping, je {CHECK_ECHOES} Echos:")
    for target in targets:
        rtts = await fixed_rate_echoes(
            icmp.echo,
            target,
            count=CHECK_ECHOES,
            period=ECHO_PERIOD_S,
            timeout=ping_settings.timeout,
        )
        shown = ", ".join("verloren" if rtt is None else f"{rtt:.1f} ms" for rtt in rtts)
        typer.echo(f"  {target:<15} {shown}")

    dns_probe = DnsProbe(settings.probes.dns_lookup)
    typer.echo(f"\nTest-DNS (Abfrage {settings.probes.dns_lookup.query}):")
    for target in dns_probe.targets():
        result = await dns_probe.measure(target)
        shown = f"{result.latency_ms:.1f} ms" if result.ok else f"FEHLER: {result.error}"
        typer.echo(f"  {target:<15} {shown}")


@app.callback()
def main() -> None:
    """RootPing – Netzwerk-Diagnose mit Messwerten statt Raten."""
