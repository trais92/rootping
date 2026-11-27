# RootPing

Ein schlankes Netzwerk-Diagnose-Tool mit KI-Agent. RootPing misst Ping (Router und Internet) und DNS, speichert die Werte in SQLite und lässt einen Claude-Agenten Störungen erkennen und erklären.

Über simulierte Netzwerkfehler (netem) wird verglichen, wie gut die KI gegenüber festen Regeln abschneidet.

> **Status:** Sprint 1 von 5. Der Messdienst läuft: Ping zum Router und ins Internet (1 Echo pro Sekunde, zusammengefasst alle 10 s mit Mittelwert, Höchstwert, Verlust und Jitter) und DNS-Abfragen, gespeichert in SQLite. Störungserkennung und KI folgen in Sprint 3 und 4 ([Projektplan](docs/projektplan.md)).

## Schnellstart

Voraussetzung ist nur [uv](https://docs.astral.sh/uv/getting-started/installation/); uv lädt die passende Python-Version selbst.

```bash
git clone https://github.com/trais92/rootping
cd rootping
uv sync
uv run rootping check   # prüft Ping-Rechte, Router, Test-Ping und DNS
uv run rootping run     # Messdienst starten, Strg+C beendet
```

## Voraussetzungen

- **Windows:** keine Adminrechte nötig, Ping läuft über die eingebaute Windows-ICMP-API wie bei `ping.exe`.
- **Linux:** Ping ohne root braucht die Kernel-Einstellung `net.ipv4.ping_group_range`, die die eigene Gruppe einschließt. Auf vielen Systemen (mit systemd) ist das schon so. Falls nicht, erklärt `rootping check` die Abhilfe ([docs/ping.md](docs/ping.md)).

## Dokumentation

| Thema | Seite |
|---|---|
| Ziel, Umfang, Sprints | [docs/projektplan.md](docs/projektplan.md) |
| Aufbau des Codes | [docs/architektur.md](docs/architektur.md) |
| Ping und DNS messen | [docs/ping.md](docs/ping.md), [docs/dns.md](docs/dns.md) |
| Messdienst (Takt, Lücken, Netzwechsel) | [docs/messdienst.md](docs/messdienst.md) |
| Konfiguration | [docs/konfiguration.md](docs/konfiguration.md), [config.example.toml](config.example.toml) |
| Datenbank | [docs/datenmodell.md](docs/datenmodell.md) |
| Entwickeln, testen, CI | [docs/entwicklung.md](docs/entwicklung.md) |
| Entscheidungen | [docs/adr/](docs/adr/README.md) |
| Technik-Recherche mit Quellen | [docs/tech-stack.md](docs/tech-stack.md) |
