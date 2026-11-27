"""Der einzige Zugriff auf die SQLite-Datenbank.

Kein anderes Modul öffnet die Datenbank oder schreibt SQL. Wer später etwas an
der Speicherung ändert (z. B. eine neue Spalte oder eine andere Datenbank),
ändert nur dieses Paket. Hintergrund: ADR-001, ``docs/datenmodell.md`` und
``docs/tech-stack.md`` Abschnitt 3.12.

Einstellungen der Verbindung und warum:

- ``journal_mode=WAL``: Der Messdienst schreibt, CLI und (später) MCP-Server
  lesen gleichzeitig, ohne sich zu blockieren.
- ``synchronous=NORMAL``: schnelle Commits; bei Stromausfall gehen höchstens
  die letzten Sekunden verloren, die Datei bleibt aber heil.
- ``foreign_keys=ON``: SQLite prüft Verweise sonst nicht.
- ``busy_timeout=5000``: kurze Sperren abwarten statt sofort einen Fehler melden.
"""

import json
import logging
import re
import sqlite3
import time
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from enum import StrEnum
from importlib import resources
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from rootping.platform.common import NetworkContext
from rootping.probes.base import ProbeResult
from rootping.timeutil import to_iso

log = logging.getLogger(__name__)

SLOW_COMMIT_MS = 50.0
"""Ab dieser Dauer wird ein Commit als Warnung geloggt (Windows: Virenscanner, NTFS)."""

_MIGRATION_NAME = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


class EventType(StrEnum):
    """Erlaubte Werte für ``events.type``."""

    GAP = "gap"
    """Messlücke, z. B. nach dem Ruhezustand."""
    NETWORK_CHANGE = "network_change"
    """Router oder Netzwerkkarte haben sich geändert (anderes WLAN, VPN)."""


class MigrationError(RuntimeError):
    """Migrationen sind falsch nummeriert, oder die Datenbank ist neuer als RootPing."""


def load_migrations() -> list[tuple[int, str]]:
    """Liest alle Migrationen aus ``rootping/storage/migrations``.

    Returns:
        Liste von (Versionsnummer, SQL-Text), aufsteigend sortiert.

    Raises:
        MigrationError: Wenn ein Dateiname nicht dem Muster ``NNN_name.sql``
            folgt oder die Nummern Lücken haben.
    """
    folder = resources.files("rootping.storage.migrations")
    migrations: list[tuple[int, str]] = []
    for entry in folder.iterdir():
        if not entry.name.endswith(".sql"):
            continue
        match = _MIGRATION_NAME.match(entry.name)
        if match is None:
            raise MigrationError(f"Ungültiger Migrationsname: {entry.name}")
        migrations.append((int(match.group(1)), entry.read_text(encoding="utf-8")))
    migrations.sort()
    expected = list(range(1, len(migrations) + 1))
    if [number for number, _ in migrations] != expected:
        raise MigrationError("Migrationen müssen lückenlos ab 001 nummeriert sein.")
    return migrations


class Storage:
    """Verbindung zur RootPing-Datenbank mit allen Lese- und Schreibfunktionen.

    Verwendung::

        with Storage.open(path) as storage:
            storage.save_measurements(results, context_id)
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Übernimmt eine fertig eingerichtete Verbindung (normalerweise über :meth:`open`).

        Args:
            connection: Verbindung mit ``autocommit=False`` und ``row_factory=sqlite3.Row``.
        """
        self._conn = connection

    @classmethod
    def open(cls, path: Path, *, read_only: bool = False) -> Self:
        """Öffnet (und erzeugt bei Bedarf) die Datenbank und bringt das Schema auf Stand.

        Args:
            path: Pfad der SQLite-Datei. Fehlende Ordner werden angelegt.
            read_only: Nur lesend öffnen (für Werkzeuge, die nichts ändern dürfen).
                Dann wird nicht migriert; die Datei muss existieren.

        Returns:
            Die geöffnete Datenbank.

        Raises:
            MigrationError: Wenn die Datei von einer neueren RootPing-Version stammt.
        """
        if read_only:
            uri = f"{path.resolve().as_uri()}?mode=ro"
            conn = sqlite3.connect(uri, uri=True, autocommit=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path, autocommit=True)
        try:
            conn.row_factory = sqlite3.Row
            # PRAGMAs vor jeder Transaktion setzen, sonst schlägt WAL fehl (Test T5).
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 5000")
            if not read_only:
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")
                _migrate(conn)
            # Ab hier gilt das Verhalten nach PEP 249: Änderungen erst mit commit() sichtbar.
            conn.autocommit = False
        except BaseException:
            conn.close()
            raise
        return cls(conn)

    def close(self) -> None:
        """Schließt die Verbindung. Nicht gespeicherte Änderungen werden verworfen."""
        self._conn.close()

    def __enter__(self) -> Self:
        """Erlaubt ``with Storage.open(...) as storage:``."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Schließt die Verbindung am Ende des ``with``-Blocks."""
        self.close()

    # --- Lesen ----------------------------------------------------------------

    def schema_version(self) -> int:
        """Gibt die Schema-Version zurück (``PRAGMA user_version``)."""
        return int(self._conn.execute("PRAGMA user_version").fetchone()[0])

    def recent_measurements(self, limit: int = 20) -> list[dict[str, Any]]:
        """Gibt die neuesten Messungen zurück, neueste zuerst.

        Args:
            limit: Höchstzahl der Zeilen.

        Returns:
            Eine Liste von Dictionaries mit den Spalten von ``measurements``.
        """
        rows = self._conn.execute(
            "SELECT * FROM measurements ORDER BY ts DESC, id DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in rows]

    def events(self) -> list[dict[str, Any]]:
        """Gibt alle Ereignisse in zeitlicher Reihenfolge zurück (``details`` als dict)."""
        rows = self._conn.execute("SELECT * FROM events ORDER BY ts, id")
        return [dict(row) | {"details": json.loads(row["details"])} for row in rows]

    # --- Schreiben --------------------------------------------------------------

    def context_id_for(self, context: NetworkContext, seen_at: datetime) -> int:
        """Gibt die ID des Netzwerk-Kontexts zurück und legt ihn bei Bedarf an.

        Args:
            context: Router und Netzwerkkarte.
            seen_at: Zeitpunkt, an dem der Kontext beobachtet wurde (für ``first_seen``).

        Returns:
            Die ID in ``network_contexts``.
        """
        with self._transaction():
            self._conn.execute(
                "INSERT INTO network_contexts (gateway, interface, first_seen) VALUES (?, ?, ?) "
                "ON CONFLICT (gateway, interface) DO NOTHING",
                (context.gateway, context.interface, to_iso(seen_at)),
            )
            row = self._conn.execute(
                "SELECT id FROM network_contexts WHERE gateway = ? AND interface = ?",
                (context.gateway, context.interface),
            ).fetchone()
        return int(row["id"])

    def save_measurements(self, results: Sequence[ProbeResult], context_id: int | None) -> None:
        """Speichert die Ergebnisse einer Messrunde in einer Transaktion.

        Args:
            results: Ergebnisse, eine Zeile pro Ergebnis.
            context_id: Netzwerk-Kontext der Runde oder ``None``, wenn kein Netz erkannt wurde.
        """
        with self._transaction():
            self._conn.executemany(
                "INSERT INTO measurements (ts, probe, target, ok, latency_ms, loss_pct, jitter_ms, "
                "max_ms, error, context_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _measurement_rows(results, context_id),
            )

    def add_event(
        self,
        event_type: EventType,
        ts: datetime,
        context_id: int | None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Speichert ein Ereignis (Messlücke oder Netzwechsel).

        Args:
            event_type: Art des Ereignisses.
            ts: Zeitpunkt.
            context_id: Betroffener Netzwerk-Kontext, falls bekannt.
            details: Zusätzliche Angaben, werden als JSON gespeichert.
        """
        with self._transaction():
            self._conn.execute(
                "INSERT INTO events (ts, type, context_id, details) VALUES (?, ?, ?, ?)",
                (to_iso(ts), event_type.value, context_id, json.dumps(details or {})),
            )

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        """Alles im Block gilt ganz oder gar nicht: Commit am Ende, Rollback bei Fehler.

        Dauert der Commit länger als :data:`SLOW_COMMIT_MS`, wird gewarnt.
        """
        try:
            yield
        except BaseException:
            self._conn.rollback()
            raise
        start = time.perf_counter()
        self._conn.commit()
        duration_ms = (time.perf_counter() - start) * 1000
        if duration_ms > SLOW_COMMIT_MS:
            log.warning("Langsamer Commit: %.0f ms", duration_ms)


def _measurement_rows(
    results: Iterable[ProbeResult], context_id: int | None
) -> Iterable[tuple[Any, ...]]:
    """Wandelt Ergebnisse in Zeilen für ``INSERT INTO measurements`` um."""
    for r in results:
        yield (
            to_iso(r.ts),
            r.probe,
            r.target,
            int(r.ok),
            r.latency_ms,
            r.loss_pct,
            r.jitter_ms,
            r.max_ms,
            r.error,
            context_id,
        )


def _migrate(conn: sqlite3.Connection) -> None:
    """Spielt alle fehlenden Migrationen der Reihe nach ein, jede in eigener Transaktion.

    Args:
        conn: Verbindung im Autocommit-Modus.

    Raises:
        MigrationError: Wenn die Datenbank neuer ist als die bekannten Migrationen.
    """
    current = int(conn.execute("PRAGMA user_version").fetchone()[0])
    migrations = load_migrations()
    if current > len(migrations):
        raise MigrationError(
            f"Die Datenbank hat Schema-Version {current}, diese RootPing-Version kennt nur "
            f"{len(migrations)}. Bitte RootPing aktualisieren."
        )
    for number, sql in migrations[current:]:
        log.info("Datenbank-Migration %03d wird eingespielt", number)
        # Alles in einer Transaktion: Entweder die ganze Migration gilt oder nichts.
        try:
            conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
