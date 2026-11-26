# ADR-010: Konfiguration in TOML, geprüft mit pydantic-settings

- **Status:** vorgeschlagen
- **Datum:** 2026-11-26

## Kontext
Alle Werte (Ziele, Intervalle, Schwellen, Modell) stehen in einer TOML-Datei (Grundregel „leicht änderbar“). In [probes.md](../probes.md) bekommt jede Probe bisher ein `dict`. Fehler wie ein Tippfehler im Schlüssel oder ein Text statt einer Zahl fielen damit erst zur Laufzeit auf. Details: [tech-stack.md](../tech-stack.md), Abschnitt 3.13, Test T8.

## Entscheidung
- TOML bleibt das Format.
- Eingelesen und geprüft mit **pydantic-settings**: ein Modell für die Gesamtkonfiguration, ein kleines Modell pro Probe-Abschnitt `[probes.<name>]`, unbekannte Schlüssel sind Fehler (`extra="forbid"`).
- Umgebungsvariablen mit Präfix `ROOTPING_` (verschachtelt mit `__`) überschreiben Werte, z. B. für Labor und CI.
- Der API-Schlüssel steht nie in der Datei; das Anthropic-SDK liest `ANTHROPIC_API_KEY`.

## Betrachtete Alternativen
- **`tomllib` + `dict`:** keine Prüfung, Fehler erst zur Laufzeit.
- **dynaconf, Hydra:** deutlich mehr Konzept als nötig.
- **YAML:** zusätzliche Abhängigkeit; TOML ist in Python eingebaut.

## Konsequenzen
- Konfigurationsfehler fallen beim Start mit klarer Meldung auf (Pfad und Grund).
- Pydantic ist ohnehin vorhanden (über `anthropic`, `mcp`, `typer`), also keine neue Grundabhängigkeit außer pydantic-settings.
- `Probe.__init__` bekommt ein typisiertes Einstellungsobjekt statt `dict` (Anpassung in `probes.md`).
