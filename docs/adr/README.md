# Architecture Decision Records (ADRs)

Ein ADR hält **eine** wichtige Entscheidung fest: Was war die Ausgangslage, was wurde entschieden, was folgt daraus? So lässt sich später nachvollziehen, *warum* etwas so ist, auch wenn man es längst vergessen hat (oder im Bewerbungsgespräch gefragt wird).

**Regeln:**
- Ein ADR pro Entscheidung, fortlaufend nummeriert, kurz (eine Bildschirmseite).
- Ein angenommenes ADR wird nicht umgeschrieben. Ändert sich die Entscheidung, gibt es ein neues ADR, das das alte „ersetzt“.
- Status: *vorgeschlagen*, *angenommen*, *ersetzt durch ADR-xxx*.

| Nr. | Titel | Status |
|---|---|---|
| [001](001-sqlite.md) | SQLite als Speicher | angenommen |
| [002](002-windows-und-linux.md) | Windows und Linux, Labor nur unter Linux | angenommen |
| [003](003-erst-regeln-dann-ki.md) | Erst Regeln, dann KI | angenommen |
| [004](004-ping-ohne-adminrechte.md) | Ping ohne Adminrechte mit icmplib | angenommen, Spike in Sprint 1 |
| [005](005-traceroute-auf-anfrage.md) | Traceroute nur auf Anfrage | angenommen |

Vorlage für neue ADRs: [000-vorlage.md](000-vorlage.md)
