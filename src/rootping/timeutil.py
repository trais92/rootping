"""Zeitstempel in genau einem Format: ISO 8601, UTC, Millisekunden, Endung ``Z``.

Das Datenmodell (``docs/datenmodell.md``) schreibt UTC-Zeitstempel als Text vor,
z. B. ``2026-11-26T11:56:00.123Z``. Alle Stellen, die Zeitpunkte erzeugen oder
speichern, nutzen diese zwei Funktionen. So gibt es keine Zeitzonen-Verwirrung
zwischen Windows und Linux.
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Gibt den aktuellen Zeitpunkt als zeitzonenbewusstes ``datetime`` in UTC zurück."""
    return datetime.now(UTC)


def to_iso(ts: datetime) -> str:
    """Wandelt einen Zeitpunkt in das Speicherformat um.

    Args:
        ts: Zeitpunkt mit Zeitzone. Andere Zeitzonen werden nach UTC umgerechnet.

    Returns:
        Text wie ``2026-11-26T11:56:00.123Z``.

    Raises:
        ValueError: Wenn ``ts`` keine Zeitzone hat. Ohne Zeitzone wäre unklar,
            welche Uhrzeit gemeint ist.
    """
    if ts.tzinfo is None:
        raise ValueError("Zeitstempel ohne Zeitzone; bitte utc_now() verwenden.")
    return ts.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
