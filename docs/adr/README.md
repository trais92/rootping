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
| [004](004-ping-ohne-adminrechte.md) | Ping ohne Adminrechte mit icmplib | ersetzt durch 006 |
| [005](005-traceroute-auf-anfrage.md) | Traceroute nur auf Anfrage | angenommen |
| [006](006-ping-ueber-betriebssystem-schnittstellen.md) | Ping über die Schnittstellen des Betriebssystems, mit festem Takt | angenommen (ersetzt 004) |
| [007](007-werkzeugkette.md) | Werkzeugkette (Python, uv, ruff, Pyright, prek) | angenommen |
| [008](008-agent-mit-messages-api.md) | Claude-Agent über die Messages API mit eigener Schleife | angenommen |
| [009](009-mcp-sdk-2.md) | MCP-Server mit dem offiziellen SDK 2.x, nur stdio, nur lesend | angenommen |
| [010](010-konfiguration-pydantic-settings.md) | Konfiguration in TOML, geprüft mit pydantic-settings | angenommen |
| [011](011-ping-ziele-nur-ipv4-adressen.md) | Ping- und DNS-Ziele sind IPv4-Adressen, keine Namen | vorgeschlagen |

Vorlage für neue ADRs: [000-vorlage.md](000-vorlage.md)
