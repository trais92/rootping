"""Konfiguration: eine TOML-Datei, geprüft mit pydantic-settings (ADR-010).

Reihenfolge, wer gewinnt (stärkste zuerst):

1. Umgebungsvariablen mit Präfix ``ROOTPING_``, Ebenen getrennt durch ``__``,
   z. B. ``ROOTPING_PROBES__PING_INTERNET__TIMEOUT=3``.
2. Die TOML-Datei (``--config`` oder ``config.toml`` im Konfigurationsordner).
3. Die Standardwerte in diesem Modul. ``config.example.toml`` zeigt sie alle.

Unbekannte Schlüssel und falsche Werte sind ein Fehler beim Start, mit Angabe
von Ort und Grund. Erklärung aller Einstellungen: ``docs/konfiguration.md``.
"""

import tomllib
from pathlib import Path
from typing import Any

import platformdirs
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from rootping.probes.dns import DnsSettings
from rootping.probes.ping import PingGatewaySettings, PingInternetSettings

APP_NAME = "rootping"


class ConfigError(Exception):
    """Die Konfiguration ist ungültig. Die Meldung ist für Menschen geschrieben."""


class ProbesSettings(BaseModel):
    """Alle Probe-Abschnitte ``[probes.<name>]``. Ein Feld pro Eintrag in ``PROBES``.

    Attributes:
        ping_gateway: Ping zum Router.
        ping_internet: Ping zu Zielen im Internet.
        dns_lookup: DNS-Abfragen.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ping_gateway: PingGatewaySettings = Field(default_factory=PingGatewaySettings)
    ping_internet: PingInternetSettings = Field(default_factory=PingInternetSettings)
    dns_lookup: DnsSettings = Field(default_factory=DnsSettings)


class ServiceSettings(BaseModel):
    """Einstellungen des Messdiensts (Abschnitt ``[service]``).

    Attributes:
        gap_seconds: Springt die Uhr zwischen zwei Prüfungen weiter als so viele
            Sekunden (z. B. Ruhezustand), wird eine Messlücke gespeichert.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    gap_seconds: float = Field(default=30, ge=5)


class Settings(BaseSettings):
    """Gesamte Konfiguration von RootPing.

    Attributes:
        database: Pfad der SQLite-Datei. Leer = Standardordner des Betriebssystems
            (siehe :func:`default_database_path`).
        service: Einstellungen des Messdiensts.
        probes: Einstellungen der einzelnen Messungen.
    """

    model_config = SettingsConfigDict(
        env_prefix="ROOTPING_",
        env_nested_delimiter="__",
        extra="forbid",
        frozen=True,
    )

    database: Path | None = None
    service: ServiceSettings = Field(default_factory=ServiceSettings)
    probes: ProbesSettings = Field(default_factory=ProbesSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Legt fest, dass Umgebungsvariablen Vorrang vor der Datei haben.

        Die Werte aus der TOML-Datei kommen als ``init_settings`` herein
        (siehe :func:`load_settings`). ``.env``-Dateien und Secret-Ordner werden
        bewusst nicht gelesen.
        """
        del settings_cls, dotenv_settings, file_secret_settings  # bewusst ungenutzt
        return (env_settings, init_settings)

    def database_path(self) -> Path:
        """Gibt den tatsächlich verwendeten Pfad der Datenbank zurück."""
        return self.database or default_database_path()


def default_config_path() -> Path:
    r"""Gibt den Standardpfad der Konfigurationsdatei zurück.

    Windows: ``%LOCALAPPDATA%\\rootping\\config.toml``,
    Linux: ``~/.config/rootping/config.toml``.
    """
    return Path(platformdirs.user_config_dir(APP_NAME, appauthor=False)) / "config.toml"


def default_database_path() -> Path:
    r"""Gibt den Standardpfad der Datenbank zurück.

    Windows: ``%LOCALAPPDATA%\\rootping\\rootping.db``,
    Linux: ``~/.local/share/rootping/rootping.db``.
    """
    return Path(platformdirs.user_data_dir(APP_NAME, appauthor=False)) / "rootping.db"


def load_settings(config_file: Path | None = None) -> Settings:
    """Liest und prüft die Konfiguration.

    Args:
        config_file: Ausdrücklich gewählte Datei. Ohne Angabe wird
            :func:`default_config_path` genommen, falls die Datei existiert;
            sonst gelten die Standardwerte.

    Returns:
        Die geprüfte Konfiguration.

    Raises:
        ConfigError: Datei fehlt (bei ausdrücklicher Angabe), ist kein gültiges
            TOML oder enthält unbekannte Schlüssel bzw. falsche Werte.
    """
    path = config_file or default_config_path()
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as err:
            raise ConfigError(f"{path}: kein gültiges TOML ({err}).") from err
    elif config_file is not None:
        raise ConfigError(f"Konfigurationsdatei nicht gefunden: {path}")

    try:
        return Settings(**data)
    except ValidationError as err:
        problems = "\n".join(
            f"  - {'.'.join(str(part) for part in e['loc'])}: {e['msg']}" for e in err.errors()
        )
        source = path if path.is_file() else "Standardwerte/Umgebungsvariablen"
        raise ConfigError(f"Ungültige Konfiguration ({source}):\n{problems}") from err
