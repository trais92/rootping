"""Kennzahlen einer Ping-Runde: Mittelwert, Maximum, Verlust und Jitter.

Reine Rechenfunktion ohne Netzwerk, damit sie auf Windows und Linux gleich
ist und vollständig getestet werden kann (auch mit Hypothesis).
Definitionen: ``docs/diagnose.md`` (Abschnitt „Jitter-Definition“) und ADR-006.
"""

from dataclasses import dataclass
from itertools import pairwise


@dataclass(frozen=True)
class PingSummary:
    """Zusammenfassung einer Runde aus mehreren Echos.

    Attributes:
        sent: Anzahl gesendeter Echos.
        received: Anzahl erhaltener Antworten.
        loss_pct: Verlust in Prozent (0 bis 100).
        avg_ms: Mittlere Antwortzeit oder ``None``, wenn keine Antwort kam.
        max_ms: Höchste Antwortzeit oder ``None``, wenn keine Antwort kam.
        jitter_ms: Jitter oder ``None`` bei weniger als zwei Antworten.
    """

    sent: int
    received: int
    loss_pct: float
    avg_ms: float | None
    max_ms: float | None
    jitter_ms: float | None


def summarize(rtts: list[float | None]) -> PingSummary:
    """Berechnet die Kennzahlen einer Ping-Runde.

    Jitter ist der Mittelwert der absoluten Differenzen aufeinanderfolgender
    Antwortzeiten. Verlorene Pakete werden übersprungen: Bei ``[20, 25, None, 22]``
    sind die Differenzen 5 und 3, der Jitter also 4 ms.

    Args:
        rtts: Antwortzeiten in Millisekunden in Sendereihenfolge;
            ``None`` steht für ein verlorenes Paket.

    Returns:
        Die Kennzahlen der Runde.

    Raises:
        ValueError: Wenn ``rtts`` leer ist (eine Runde ohne Echo ist ein Programmfehler).
    """
    if not rtts:
        raise ValueError("Eine Ping-Runde braucht mindestens ein Echo.")

    received = [rtt for rtt in rtts if rtt is not None]
    sent = len(rtts)
    loss_pct = 100.0 * (sent - len(received)) / sent

    if not received:
        return PingSummary(sent, 0, loss_pct, avg_ms=None, max_ms=None, jitter_ms=None)

    diffs = [abs(b - a) for a, b in pairwise(received)]
    jitter = sum(diffs) / len(diffs) if diffs else None
    return PingSummary(
        sent=sent,
        received=len(received),
        loss_pct=loss_pct,
        avg_ms=sum(received) / len(received),
        max_ms=max(received),
        jitter_ms=jitter,
    )
