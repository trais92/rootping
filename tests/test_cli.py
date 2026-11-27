"""Tests für die Kommandozeile mit gefälschtem Netzwerk."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

import rootping.platform
from rootping import cli, logsetup
from rootping.platform import NetworkContext
from rootping.probes import ping
from rootping.storage import Storage

runner = CliRunner()


@pytest.fixture
def fake_network(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ersetzt alle Netzwerk- und Betriebssystem-Aufrufe durch Fälschungen."""

    async def echo(target: str, timeout: float) -> float | None:
        return 5.0

    monkeypatch.setattr(rootping.platform, "echo", echo)
    monkeypatch.setattr(
        rootping.platform, "default_route", lambda: NetworkContext("192.168.1.1", "eth0")
    )
    monkeypatch.setattr(rootping.platform, "ping_permission_problem", lambda: None)
    monkeypatch.setattr(ping, "ECHO_PERIOD_S", 0.01)
    monkeypatch.setattr(logsetup, "default_log_dir", lambda: tmp_path / "logs")
    monkeypatch.setattr("rootping.config.default_config_path", lambda: tmp_path / "fehlt.toml")


def write_config(tmp_path: Path) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(
        f'database = "{(tmp_path / "r.db").as_posix()}"\n'
        "[probes.ping_gateway]\ninterval = 2\n"
        '[probes.ping_internet]\ninterval = 2\ntargets = ["1.1.1.1"]\n',
        encoding="utf-8",
    )
    return path


@pytest.mark.usefixtures("fake_network", "restore_logging")
def test_run_measures_and_stores(tmp_path: Path) -> None:
    result = runner.invoke(
        cli.app, ["run", "--config", str(write_config(tmp_path)), "--rounds", "1"]
    )
    assert result.exit_code == 0, result.output
    assert "ping_gateway" in result.output
    assert "192.168.1.1" in result.output
    with Storage.open(tmp_path / "r.db") as db:
        rows = db.recent_measurements()
    assert {(r["probe"], r["target"]) for r in rows} == {
        ("ping_gateway", "192.168.1.1"),
        ("ping_internet", "1.1.1.1"),
    }
    assert all(r["latency_ms"] == 5.0 and r["loss_pct"] == 0.0 for r in rows)


@pytest.mark.usefixtures("fake_network", "restore_logging")
def test_run_stops_with_clear_message_without_ping_rights(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rootping.platform, "ping_permission_problem", lambda: "Bitte freigeben")
    result = runner.invoke(cli.app, ["run", "--config", str(write_config(tmp_path))])
    assert result.exit_code == 3
    assert "Bitte freigeben" in result.output


@pytest.mark.usefixtures("fake_network")
def test_check_reports_router_and_test_pings(tmp_path: Path) -> None:
    result = runner.invoke(cli.app, ["check", "--config", str(write_config(tmp_path))])
    assert result.exit_code == 0, result.output
    assert "Ping-Rechte:   OK" in result.output
    assert "192.168.1.1 über eth0" in result.output
    assert "5.0 ms, 5.0 ms, 5.0 ms" in result.output


@pytest.mark.usefixtures("fake_network")
def test_invalid_config_gives_exit_code_2(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("[probes.ping_internet]\ntimeout = -1\n", encoding="utf-8")
    result = runner.invoke(cli.app, ["check", "--config", str(bad)])
    assert result.exit_code == 2
    assert "probes.ping_internet.timeout" in result.output
