# Entwicklung: einrichten, prüfen, testen

> Stand 27.11.2026 · Werkzeuge: [ADR-007](adr/007-werkzeugkette.md)

## Einrichten (Windows und Linux gleich)

Voraussetzung ist nur [uv](https://docs.astral.sh/uv/). uv lädt die passende Python-Version selbst.

```bash
git clone https://github.com/trais92/rootping
cd rootping
uv sync                 # Umgebung mit allen Abhängigkeiten aus uv.lock
uv run rootping check   # Umgebung prüfen (Ping-Rechte, Router, Test-Ping, DNS)
uv run rootping run     # Messdienst starten, Strg+C beendet
```

Optional, Git-Hooks (prüfen vor jedem Commit dasselbe wie die CI):

```bash
uv tool install prek
prek install
```

## Die vier Prüfungen

Genau diese laufen auch in der CI:

| Befehl | Prüft |
|---|---|
| `uv run ruff check .` | Fehlerquellen, fehlende Docstrings, `print`, Zeitstempel ohne Zeitzone, blockierende Aufrufe in `async`-Funktionen … ([tech-stack.md](tech-stack.md) 3.4) |
| `uv run ruff format --check .` | einheitliche Formatierung (`ruff format .` korrigiert) |
| `uv run pyright` | Typen (Modus `standard`) |
| `uv run pytest` | Tests |

Tipp: `uv run pyright --pythonplatform Windows` prüft unter Linux auch den Windows-Code.

## Tests

| Datei | Prüft |
|---|---|
| `test_summary.py` | Kennzahlen, mit Hypothesis (z. B. „Verlust immer zwischen 0 und 100 %“) |
| `test_ping_probe.py` | fester Takt, Zusammenfassung, Router-Platzhalter, Prüfung der Einstellungen |
| `test_dns.py` | DNS-Abfragen gegen einen Test-Server auf 127.0.0.1, alle Fehlerarten |
| `test_scheduler.py` | Takt, Sicherheitsnetz, Messlücken, Netzwechsel |
| `test_storage.py` | Migrationen, `STRICT`, WAL, Nur-Lesen, Rollback |
| `test_config.py` | Datei, Umgebungsvariablen, Fehlermeldungen, Beispieldatei = Standardwerte |
| `test_cli.py` | `run` und `check` mit gefälschtem Netzwerk |
| `test_platform_linux.py` / `_windows.py` | Betriebssystem-Teil, nur auf dem jeweiligen System; echter Ping an 127.0.0.1 |

- Tests brauchen **kein Internet**. Netzwerkaufrufe werden ersetzt; echte Pings gehen nur an `127.0.0.1` (Marker `loopback`).
- Fehlen lokal unter Linux die Ping-Rechte, wird der Loopback-Test übersprungen. In der CI (`CI` gesetzt) schlägt er stattdessen fehl.
- Hilfen für Tests (`FakeProbe`, temporäre Datenbank) stehen in `tests/conftest.py`.
- Warnungen gelten in Tests als Fehler (`filterwarnings = error`), damit z. B. nicht geschlossene Datenbankverbindungen auffallen.

## CI

`.github/workflows/ci.yml` läuft bei jedem Pull Request und jedem Push auf `main`:

- Matrix **Windows und Linux × Python 3.14 und 3.15**, jeweils die vier Prüfungen oben. Auf Linux wird vorher Ping ohne root freigegeben, weil die GitHub-Runner den Kernel-Standard `1 0` haben ([ping.md](ping.md)).
- Ein Job prüft die Workflows mit **zizmor** auf Sicherheitsprobleme.
- Actions sind auf volle Commit-SHAs gepinnt, Rechte auf `contents: read` begrenzt.
- Dependabot schlägt wöchentlich Updates vor, mit 7 Tagen Cooldown.

**Grenze:** Die Windows-Runner laufen als Administrator. Dass der Ping ohne Admin geht, zeigt erst `rootping check` auf einem normalen Konto ([ping.md](ping.md#test-ohne-adminrechte-offener-punkt-aus-sprint-0)).

## Abhängigkeiten ändern

```bash
uv add paketname        # Laufzeit
uv add --dev paketname  # nur Entwicklung
```

`pyproject.toml` hat `exclude-newer = "7 days"`: Versionen, die jünger als eine Woche sind, werden nicht genommen. Untergrenzen deshalb auf eine getestete Minor-Version setzen (z. B. `>=2.9`), die genaue Version hält `uv.lock` fest.
