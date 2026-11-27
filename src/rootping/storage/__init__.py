"""Speicherung in SQLite. Einziger Ort, der die Datenbank kennt (``docs/datenmodell.md``)."""

from rootping.storage.database import EventType, MigrationError, Storage

__all__ = ["EventType", "MigrationError", "Storage"]
