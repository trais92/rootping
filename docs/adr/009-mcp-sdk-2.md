# ADR-009: MCP-Server mit dem offiziellen SDK 2.x, nur stdio, nur lesend

- **Status:** vorgeschlagen
- **Datum:** 2026-11-26

## Kontext
Der Plan sah das „offizielle MCP Python SDK“ vor. Seit 28.07.2026 ist Version 2.0 stabil; 1.x ist im Wartungsmodus. In 2.x heißt `FastMCP` jetzt `MCPServer`, und Attributnamen sind snake_case. Viele Anleitungen zeigen noch den alten Stil. Details: [tech-stack.md](../tech-stack.md), Abschnitt 3.19, Test T4.

## Entscheidung
- `mcp>=2.3,<3`, Server-Klasse `MCPServer` (`from mcp.server.mcpserver import MCPServer`).
- Transport **nur stdio** (lokal mit Claude Desktop/Code), kein HTTP-Port.
- Werkzeuge sind dünne Hüllen um `tools.py`; Rückgaben als Pydantic-Modelle (ergeben ein Ausgabe-Schema).
- Der MCP-Server öffnet die Datenbank **nur lesend** (`file:…?mode=ro`).
- Der MCP-Prozess schreibt nie auf stdout außer MCP-Nachrichten (Logs nach stderr bzw. Datei; ruff-Regel `T201`).

## Betrachtete Alternativen
- **MCP SDK 1.x:** nur noch Wartung.
- **Eigenständiges Paket FastMCP (4.x):** mehr Funktionen für gehostete Server, für einen lokalen stdio-Server nicht nötig.
- **Streamable HTTP:** offener Port und Authentifizierung nötig, ohne Nutzen für lokale Clients.
- **Agent nutzt den eigenen MCP-Server** (über `anthropic.lib.tools.mcp`): elegant, aber zusätzlicher Prozess und Beta-Helfer; direkter Aufruf von `tools.py` erreicht dasselbe einfacher.

## Konsequenzen
- KI-Werkzeuge können die Datenbank nicht verändern.
- Aktive Werkzeuge (`ping_now`, `traceroute_now`) validieren ihre Eingaben und haben Rate-Limits (ADR-005).
- Die MCP-Spezifikation 2026-07-28 (zustandslos) wird vom SDK unterstützt; im Test wurde noch die Handshake-Version 2025-11-25 ausgehandelt. Für RootPing ohne Auswirkung.
