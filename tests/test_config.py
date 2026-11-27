"""Tests für das Einlesen und Prüfen der Konfiguration."""

import os
import tomllib
from pathlib import Path

import pytest

from rootping.config import ConfigError, Settings, load_settings
from rootping.probes import PROBES

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Sorgt dafür, dass eine echte config.toml des Entwicklers die Tests nicht beeinflusst."""
    monkeypatch.setattr("rootping.config.default_config_path", lambda: tmp_path / "fehlt.toml")
    for name in list(os.environ):
        if name.startswith("ROOTPING_"):
            monkeypatch.delenv(name)


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_without_file_defaults_apply() -> None:
    s = load_settings()
    assert s.probes.ping_internet.targets == ["1.1.1.1", "9.9.9.9"]
    assert s.service.gap_seconds == 30


def test_file_values_override_defaults(tmp_path: Path) -> None:
    path = write(tmp_path, '[probes.ping_internet]\ntargets = ["8.8.8.8"]\ntimeout = 1\n')
    s = load_settings(path)
    assert s.probes.ping_internet.targets == ["8.8.8.8"]
    assert s.probes.ping_internet.timeout == 1
    assert s.probes.ping_internet.interval == 10  # nicht angegeben → Standard


def test_environment_overrides_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = write(tmp_path, "[probes.ping_internet]\ntimeout = 1\n")
    monkeypatch.setenv("ROOTPING_PROBES__PING_INTERNET__TIMEOUT", "3")
    s = load_settings(path)
    assert s.probes.ping_internet.timeout == 3
    assert s.probes.ping_internet.targets == ["1.1.1.1", "9.9.9.9"]


def test_typo_in_key_names_the_location(tmp_path: Path) -> None:
    path = write(tmp_path, "[probes.ping_internet]\nintervall = 10\n")
    with pytest.raises(ConfigError, match=r"probes\.ping_internet\.intervall"):
        load_settings(path)


def test_hostname_as_ping_target_is_rejected(tmp_path: Path) -> None:
    path = write(tmp_path, '[probes.ping_internet]\ntargets = ["example.com"]\n')
    with pytest.raises(ConfigError, match="allow_hostnames"):
        load_settings(path)


def test_hostname_as_ping_target_with_opt_in(tmp_path: Path) -> None:
    path = write(
        tmp_path, '[probes.ping_internet]\ntargets = ["example.com"]\nallow_hostnames = true\n'
    )
    assert load_settings(path).probes.ping_internet.targets == ["example.com"]


def test_missing_explicit_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="nicht gefunden"):
        load_settings(tmp_path / "gibt-es-nicht.toml")


def test_broken_toml(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="kein gültiges TOML"):
        load_settings(write(tmp_path, "[probes\n"))


def test_database_path_default_and_override(tmp_path: Path) -> None:
    assert load_settings().database_path().name == "rootping.db"
    s = load_settings(write(tmp_path, f'database = "{(tmp_path / "x.db").as_posix()}"\n'))
    assert s.database_path() == tmp_path / "x.db"


def test_every_registered_probe_has_a_config_section() -> None:
    # PROBES und ProbesSettings müssen dieselben Namen haben (docs/probes.md).
    assert set(PROBES) == set(Settings().probes.model_dump())


def test_example_config_equals_defaults() -> None:
    # config.example.toml dokumentiert die Standardwerte; sie darf nicht veralten.
    example = tomllib.loads((REPO_ROOT / "config.example.toml").read_text(encoding="utf-8"))
    assert Settings(**example).model_dump() == Settings().model_dump()
