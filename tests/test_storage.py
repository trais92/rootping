"""Tests für die Speicherung: Migrationen, Schreiben, Lesen, Schutzmechanismen."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rootping.platform import NetworkContext
from rootping.probes.base import ProbeResult
from rootping.storage import EventType, MigrationError, Storage
from rootping.storage.database import load_migrations

TS = datetime(2026, 11, 27, 10, 0, 0, 123000, tzinfo=UTC)


def result(**overrides: object) -> ProbeResult:
    values: dict[str, object] = {
        "probe": "ping_internet",
        "target": "1.1.1.1",
        "ts": TS,
        "ok": True,
        "latency_ms": 12.5,
        "loss_pct": 10.0,
        "jitter_ms": 1.5,
        "max_ms": 20.0,
        "error": None,
    }
    values.update(overrides)
    return ProbeResult(**values)  # pyright: ignore[reportArgumentType]


def test_new_database_is_migrated(storage: Storage) -> None:
    assert storage.schema_version() == len(load_migrations()) >= 1


def test_reopening_does_not_migrate_twice(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    Storage.open(path).close()
    with Storage.open(path) as again:
        assert again.schema_version() == len(load_migrations())


def test_wal_mode_is_active(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    Storage.open(path).close()
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()


def test_save_and_read_measurement(storage: Storage) -> None:
    ctx = storage.context_id_for(NetworkContext("192.168.178.1", "eth0"), TS)
    storage.save_measurements([result()], ctx)
    [row] = storage.recent_measurements()
    assert row["ts"] == "2026-11-27T10:00:00.123Z"
    assert row["ok"] == 1
    assert row["latency_ms"] == 12.5
    assert row["context_id"] == ctx


def test_measurement_without_network_has_no_context(storage: Storage) -> None:
    storage.save_measurements([result(ok=False, error="no_gateway", target="auto")], None)
    assert storage.recent_measurements()[0]["context_id"] is None


def test_known_network_reuses_context(storage: Storage) -> None:
    home = NetworkContext("192.168.178.1", "eth0")
    first = storage.context_id_for(home, TS)
    other = storage.context_id_for(NetworkContext("10.8.0.1", "tun0"), TS)
    assert storage.context_id_for(home, TS) == first != other


def test_strict_table_rejects_wrong_type(storage: Storage) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        storage.save_measurements([result(latency_ms="schnell")], None)


def test_loss_outside_range_is_rejected(storage: Storage) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        storage.save_measurements([result(loss_pct=120.0)], None)


def test_failed_insert_leaves_nothing_behind(storage: Storage) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        storage.save_measurements([result(), result(loss_pct=-1.0)], None)
    assert storage.recent_measurements() == []


def test_events_store_details_as_json(storage: Storage) -> None:
    storage.add_event(EventType.GAP, TS, None, {"gap_seconds": 3600})
    [event] = storage.events()
    assert event["type"] == "gap"
    assert event["details"] == {"gap_seconds": 3600}


def test_naive_timestamp_is_rejected(storage: Storage) -> None:
    with pytest.raises(ValueError, match="ohne Zeitzone"):
        storage.save_measurements([result(ts=datetime(2026, 1, 1))], None)  # noqa: DTZ001


def test_read_only_cannot_write(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    Storage.open(path).close()
    with Storage.open(path, read_only=True) as ro:
        assert ro.recent_measurements() == []
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            ro.save_measurements([result()], None)


def test_database_from_newer_version_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA user_version = 999")
    conn.close()
    with pytest.raises(MigrationError, match="999"):
        Storage.open(path)


def test_migration_files_are_numbered_without_gaps() -> None:
    numbers = [number for number, _ in load_migrations()]
    assert numbers == list(range(1, len(numbers) + 1))
