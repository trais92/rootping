# Konfiguration

> Stand 27.11.2026 · Code: `src/rootping/config.py` · Entscheidung: [ADR-010](adr/010-konfiguration-pydantic-settings.md)

## Wo die Werte herkommen

Stärkste Quelle zuerst:

1. **Umgebungsvariablen** mit Präfix `ROOTPING_`, Ebenen getrennt durch `__`:
   `ROOTPING_PROBES__PING_INTERNET__TIMEOUT=3`. Listen als JSON: `ROOTPING_PROBES__PING_INTERNET__TARGETS='["8.8.8.8"]'`.
2. **TOML-Datei:** `rootping run --config datei.toml` oder, ohne Angabe, `config.toml` im Konfigurationsordner:
   - Windows: `%LOCALAPPDATA%\rootping\config.toml`
   - Linux: `~/.config/rootping/config.toml`
3. **Standardwerte** im Code. [`config.example.toml`](../config.example.toml) zeigt sie alle mit Kommentaren.

In die Datei kommen nur Werte, die man ändern will. `rootping check` zeigt, welche Datei gerade gilt.

## Prüfung beim Start

Jeder Abschnitt ist ein Pydantic-Modell. Unbekannte Schlüssel und falsche Werte sind ein Fehler, bevor irgendetwas gemessen wird:

```
Fehler in der Konfiguration:
Ungültige Konfiguration (C:\Users\kai\AppData\Local\rootping\config.toml):
  - probes.ping_internet.intervall: Extra inputs are not permitted
```

## Alle Einstellungen

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `database` | Datenordner des Systems | Pfad der SQLite-Datei. Windows: `%LOCALAPPDATA%\rootping\rootping.db`, Linux: `~/.local/share/rootping/rootping.db` |
| `service.gap_seconds` | 30 | Uhr springt weiter → Messlücke (mindestens 5) |
| `probes.<name>.enabled` | true | Probe an oder aus |
| `probes.<name>.interval` | 10 (Ping), 30 (DNS) | Sekunden pro Runde; bei Ping ganze Zahl, weil 1 Echo pro Sekunde |
| `probes.<name>.timeout` | 2 (Ping), 3 (DNS) | Sekunden Wartezeit pro Echo bzw. Abfrage (höchstens 30) |
| `probes.ping_gateway.targets` | `["auto"]` | `"auto"` = Router erkennen, sonst IPv4-Adressen |
| `probes.ping_internet.targets` | `["1.1.1.1", "9.9.9.9"]` | nur IPv4-Adressen ([ADR-011](adr/011-ping-ziele-nur-ipv4-adressen.md)) |
| `probes.dns_lookup.targets` | `["gateway", "system", "1.1.1.1"]` | siehe [dns.md](dns.md) |
| `probes.dns_lookup.query` | `"example.com"` | abgefragter Name; blockt ein Pi-hole ihn, meldet RootPing `blocked` |
| `probes.dns_lookup.only_system_with_vpn` | `true` | bei aktivem VPN nur `system` messen ([dns.md](dns.md#vpn)) |

Die Schwellen für „auffällig“ und „Störung“ ([diagnose.md](diagnose.md)) kommen in Sprint 3 als Abschnitt `[thresholds]` dazu.

## Eine Einstellung hinzufügen

1. Feld im passenden Modell ergänzen (z. B. `PingSettings` in `probes/ping.py`), mit Standardwert, Prüfung (`Field(gt=0)` …) und Beschreibung im Docstring.
2. Dieselbe Zeile mit Kommentar in `config.example.toml` eintragen. Ein Test (`test_example_config_equals_defaults`) schlägt fehl, wenn Code und Beispieldatei auseinanderlaufen.
3. Diese Tabelle ergänzen.

**Warum stehen die Standardwerte im Code und nicht in einer mitgelieferten Datei?** So gibt es genau eine Quelle der Wahrheit, die Pyright und die Tests prüfen können. Die Beispieldatei ist Doku und wird gegen den Code getestet.
