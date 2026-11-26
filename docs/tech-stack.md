# Technische Grundlage (Tech-Stack)

> Sprint 0 · Stand **26.11.2026** · gehört zu [projektplan.md](projektplan.md), [probes.md](probes.md), [datenmodell.md](datenmodell.md), [diagnose.md](diagnose.md)
> Status: **Vorschlag, in Klärung mit Kai.** Die neuen ADRs 006–010 stehen auf „vorgeschlagen“, bis Kai die offenen Entscheidungen (Abschnitt 5) bestätigt hat.

Dieses Dokument prüft jeden Baustein der bisherigen Technik-Planung gegen aktuelle Alternativen und gibt pro Bereich eine Empfehlung mit Begründung und Quellen. Wo der bisherige Plan schon die beste Wahl ist, steht das ausdrücklich da.

---

## 0. Wie geprüft wurde (und was nicht)

**Methode**

| Art | Was genau |
|---|---|
| Versionen | Live aus der PyPI-JSON-API abgefragt (`https://pypi.org/pypi/<paket>/json`) am 26.11.2026 [Q8]. Tabelle in [Anhang A](#anhang-a-versionen-stand-26112026). |
| Primärquellen | Offizielle Doku (python.org, Microsoft Learn, Kernel-Doku, MCP-Spezifikation, Anthropic-Doku, GitHub-Doku), Release Notes, Changelogs. Sekundärquellen (Blogs, Vergleiche) nur, wo es keine Primärquelle gibt; sie sind als solche markiert. |
| Quellcode | Wo die Doku nicht reicht, wurde der Quellcode gelesen, vor allem `icmplib` 3.0.4 (Befund B1/B2). |
| Eigene Tests | In einem Linux-Container mit **Python 3.15.2, uv 0.13.10**, allen Kandidaten-Bibliotheken in aktuellen Versionen. Skripte und Ausgaben in [recherche/belege.md](recherche/belege.md), nummeriert **T1–T10**. |

**Grenzen (ehrlich)**

- **Kein Windows-Rechner verfügbar.** Alle Windows-Aussagen stützen sich auf Microsoft-Doku und Quellcode, nicht auf eigene Läufe. Die GitHub-Windows-Runner helfen hier nur bedingt, weil sie **als Administrator laufen** [Q37]. Ein „ohne Admin“-Test muss auf Kais PC in einem normalen (nicht erhöhten) Terminal laufen. Der Befehl dafür steht in Abschnitt 5.
- **Keine Claude-API-Aufrufe.** Es wurde nichts ausgegeben; Aussagen zur Anthropic-API stammen aus der offiziellen Doku und aus dem installierten SDK (Signaturen geprüft, T7).
- **Externe Pings waren in der Testumgebung gesperrt.** Ping wurde gegen `127.0.0.1` getestet; Paketverlust wurde mit dem gesperrten Ziel `1.1.1.1` erzeugt (jedes Echo geht verloren). Das reicht für die Aussagen zu Rechten und Takt, nicht für echte Latenzwerte.
- **Sekundärquellen zu Typprüfern** (Konformitätszahlen) stammen aus einem Blog vom April/Mai 2026 [Q31]; sie können sich seitdem verändert haben.

**Legende:** ✅ bleibt wie geplant · 🔁 ändern · ➕ neu · ❓ Entscheidung durch Kai

---

## 1. Kurzfassung

| # | Bereich | Bisher | Empfehlung | |
|---|---|---|---|---|
| 1 | Python-Version | 3.12+ | **Untergrenze 3.14, entwickelt wird auf 3.15**; CI testet beide | 🔁 ❓ |
| 2 | Paketverwaltung | uv | **uv** (0.13), Lockfile, `exclude-newer = "7 days"` | ✅ ➕ |
| 3 | Projektlayout | offen | **src-Layout**, Build-Backend `uv_build` | ➕ |
| 4 | Linting/Formatierung | ruff | **ruff** mit Regeln, die genau Kais Grundregeln und die RootPing-Risiken abdecken | ✅ ➕ |
| 5 | Typprüfung | offen | **Pyright** (verbindlich in CI); ty beobachten | ➕ ❓ |
| 6 | Git-Hooks | offen | **prek** mit Standard-`.pre-commit-config.yaml` | ➕ |
| 7 | Nebenläufigkeit | asyncio | **asyncio** mit `TaskGroup` und `asyncio.timeout`; eigener kleiner Scheduler statt APScheduler | ✅ |
| 8 | **Ping** | icmplib, Windows ungeprüft | **Eigenes Ping-Modul mit zwei Backends:** Linux über ICMP-Datagram-Socket (icmplib), **Windows über die Windows-ICMP-API** (`IcmpSendEcho2`), **fester 1-s-Takt** | 🔁 ❓ |
| 9 | Gateway-Erkennung | `Get-NetRoute`/`route print` | Linux `/proc/net/route`, Windows `GetBestRoute` (beides ohne Unterprozess) | 🔁 |
| 10 | DNS | dnspython | **dnspython** (2.9) | ✅ ➕ |
| 11 | Traceroute | System-Befehl | System-Befehl bleibt, aber **Bytes lesen und selbst dekodieren** (Python 3.15 ändert die Standard-Kodierung) | ✅ ➕ |
| 12 | SQLite | stdlib, `user_version` | **stdlib `sqlite3`**, `STRICT`-Tabellen, WAL, eigener Migrations-Runner | ✅ ➕ |
| 13 | Konfiguration | TOML | **TOML + pydantic-settings** (Validierung, Umgebungsvariablen) | ✅ ➕ |
| 14 | CLI | typer | **Typer** (0.29), Minor-Version festhalten | ✅ |
| 15 | Logging | offen | **stdlib `logging`**, eine Datei pro Prozess, MCP-Server nie auf stdout | ➕ |
| 16 | Tests | pytest | **pytest 9, pytest-asyncio 1.x, Hypothesis** für Rechenlogik | ✅ ➕ |
| 17 | CI | GitHub Actions Win + Linux | Matrix **Windows/Linux × 3.14/3.15**, `uv sync --locked`, Actions auf SHA + Workflow-Lockfile | ✅ ➕ |
| 18 | Doku-Werkzeuge | Markdown | **Markdown im Repo + Mermaid**, Docstrings im Google-Stil (von ruff erzwungen); keine Doku-Website in v1 | ✅ |
| 19 | MCP | offizielles SDK | **MCP Python SDK 2.x** (`MCPServer`), nur stdio, Datenbank nur lesend | ✅ 🔁 |
| 20 | KI-Anbindung | Anthropic SDK | **Anthropic SDK 2.x, Messages API mit eigener kleiner Agent-Schleife**; kein Agent SDK, keine Managed Agents | ✅ ❓ |
| 21 | Verteilung Windows | offen | **`uv tool install`** aus dem Git-Repo; keine `.exe` in v1 | ➕ |
| 22 | Lieferkette | offen | Lockfile, Cooldown, Dependabot mit Cooldown, Actions gepinnt, zizmor, minimale Rechte | ➕ |

**Ehrliches Gesamturteil:** Die Grundrichtung des Plans (Python, uv, ruff, pytest, asyncio, dnspython, SQLite, TOML, MCP-SDK, Anthropic-SDK, CI auf beiden Systemen) ist **richtig und Stand der Technik**. Es gibt aber **einen echten Fehler** im Plan (Ping unter Windows, B1), **einen Konstruktionsfehler** in der Probe-Konfiguration (Takt bei Paketverlust, B2) und mehrere Stellen, an denen sich die Werkzeuge seit dem Planentwurf verändert haben (MCP SDK 2.0, Anthropic SDK 2.0, Python 3.15). Das ist kein Grund für einen anderen Stack, sondern für gezielte Korrekturen.

---

## 2. Die drei wichtigsten Befunde

### B1: `icmplib` mit `privileged=False` braucht unter Windows trotzdem Adminrechte

ADR-004 nimmt an, dass `icmplib` mit `privileged=False` ohne Admin läuft und das nur noch „bestätigt“ werden muss. **Der Quellcode zeigt, dass das unter Windows nicht stimmen kann:**

```python
# icmplib 3.0.4, icmplib/sockets.py, Zeilen 81–90 [Q9]
# The Linux kernel allows unprivileged users to use datagram
# sockets (SOCK_DGRAM) to send ICMP requests. This feature is
# now supported by the majority of Unix systems.
# Windows is not compatible.
self._privileged = privileged or PLATFORM_WINDOWS
...
socket.SOCK_RAW if self._privileged else socket.SOCK_DGRAM
```

Unter Windows wird also **immer ein Raw Socket** geöffnet; die README sagt dazu „Only available on Unix systems. Ignored on Windows.“ [Q9]. Microsoft dokumentiert: *„only members of the Administrators group can create sockets of type SOCK_RAW on Windows 2000 and later“* und *„otherwise raw socket calls will fail with an error code of WSAEACCES“* [Q10]. `icmplib` fängt genau diesen Fehler (Winsock-Code 10013) ab und wirft `SocketPermissionError` (sockets.py, Zeile 96).

**Warum funktioniert `ping.exe` dann ohne Admin?** Weil es keine Raw Sockets nutzt, sondern die Windows-ICMP-API `IcmpSendEcho`/`IcmpSendEcho2` aus `Iphlpapi.dll` [Q11][Q13]. Diese API steht jedem Programm zur Verfügung und lässt sich aus Python über `ctypes` (Standardbibliothek) aufrufen.

**Folge:** ADR-004 wird durch [ADR-006](adr/006-ping-ueber-betriebssystem-schnittstellen.md) ersetzt. Plan B (System-`ping` aufrufen) ist nicht mehr nötig, bleibt aber als Notlösung dokumentiert.

### B2: `icmplib.async_ping(count=10)` hält keinen 1-Sekunden-Takt ein

`async_ping` sendet ein Paket, **wartet auf die Antwort oder den Timeout**, schläft dann `interval` Sekunden und sendet das nächste (ping.py, Schleife in `async_ping`) [Q9]. Ein verlorenes Paket kostet also `timeout + interval` = 2 s + 1 s = 3 s statt 1 s.

Gemessen (T3): Mit 5 Paketen und vollständigem Verlust dauerte `async_ping` **14,0 s**; ein Takt, der jede Sekunde unabhängig von Antworten sendet, brauchte **6,0 s** (4 s Takt + 2 s Timeout für das letzte Echo). Hochgerechnet auf die geplanten 10 Pakete pro Runde: bis zu **29 s statt rund 11 s** (9 s Takt + 2 s Timeout des letzten Echos).

Das trifft das Projekt an der empfindlichsten Stelle: Genau bei Störungen (Verlust) würden Runden länger, weniger Runden entstünden, und die Regel „3 auffällige Runden ≈ 30 s“ aus [diagnose.md](diagnose.md) würde zu „bis zu 90 s“. Außerdem passt die Konfiguration in [probes.md](probes.md) (`interval = 10`, `count = 10`, `packet_interval = 1`, `timeout = 2`) dann nicht mehr zusammen, weil eine Runde länger als ihr Intervall dauern kann.

**Folge:** Das Ping-Modul sendet in einem **festen Takt** (jede Sekunde ein Echo, jedes mit eigenem Timeout, Antworten werden nicht abgewartet). Die Statistik (Mittel, Maximum, Verlust, Jitter) berechnet RootPing **selbst** aus der Liste der Einzelwerte, statt sie aus `icmplib` zu übernehmen. Details in Abschnitt 3.8.

### B3: Unprivilegierter Ping unter Linux ist nicht „überall Standard“

ADR-004 sagt, `net.ipv4.ping_group_range` sei „bei den meisten Distributionen Standard“. Genauer: Der **Kernel-Standard ist `1 0`**, also *„nobody (not even root) may create ping sockets“* [Q14]. Erst **systemd** setzt in `sysctl.d/50-default.conf` den Wert `0 2147483647` [Q15]; Fedora hat das z. B. mit Fedora 31 eingeführt [Q16]. Systeme ohne systemd und viele Container haben weiterhin `1 0`. In der Testumgebung war genau das der Fall (T2): erst `SocketPermissionError`, nach Setzen des Werts lief der Ping.

**Folge:** RootPing prüft das beim Start und gibt eine verständliche Meldung mit dem Befehl zur Abhilfe aus. Im Labor (Docker) wird der Wert im Compose-File gesetzt (`sysctls:`), oder RootPing läuft dort als root.

---

## 3. Die Bereiche im Einzelnen

Jeder Abschnitt hat dieselbe Gliederung: **Empfehlung**, **Begründung**, **Verworfen**, **Unsicher**.

### 3.1 Python-Version 🔁 ❓

**Empfehlung:** `requires-python = ">=3.14"`, Entwicklung auf **3.15** (Datei `.python-version`), CI testet **3.14 und 3.15**.

**Begründung**
- Stand laut Python Developer's Guide (abgerufen 26.11.2026) [Q1]: 3.10 ist seit 01.10.2026 am Lebensende; **3.11–3.13 bekommen nur noch Sicherheitsupdates**; **3.14 und 3.15 sind im „bugfix“-Status** (Supportende 2030-10 bzw. 2031-10). 3.12, die bisherige Untergrenze, bekommt also keine normalen Fehlerkorrekturen mehr.
- 3.15.0 erschien am 09.10.2026, aktuell ist **3.15.2** [Q2]; uv bietet 3.15.2 und 3.14.10 an (T1).
- Alle benötigten Pakete haben fertige Wheels für 3.15 unter Windows, auch die kompilierten (`pydantic-core`, `jiter`, `pywin32`, `cffi`, `cryptography`, `rpds-py`; geprüft über PyPI, Anhang A). Das ganze Kandidaten-Set ließ sich unter 3.15.2 installieren und ausführen (T1).
- Mehrere Kernbibliotheken verlangen inzwischen mindestens 3.11 (dnspython 2.9, platformdirs 4.14, Typer 0.29, pydantic-settings 2.16, Hypothesis 6.170) [Q8]; Typer hat 3.10 am 18.11.2026 gestrichen [Q35]. Eine hohe Untergrenze ist also ohnehin der Trend.
- Nützlich ab 3.14: `python -m asyncio ps PID` / `pstree PID` zeigt laufende asyncio-Tasks eines Prozesses [Q5], praktisch zum Erklären und Debuggen des Schedulers; verzögerte Auswertung von Annotationen (PEP 649) [Q5].
- Nützlich ab 3.15: UTF-8 ist Standard-Kodierung (PEP 686) [Q3][Q2], was Windows und Linux angleicht; „lazy imports“ (PEP 810) für schnelleren CLI-Start [Q2].
- Weil `uv` die passende Python-Version selbst herunterlädt, müssen Nutzer kein bestimmtes Python installiert haben. Die Untergrenze schränkt also kaum jemanden ein.

**Wichtige Nebenwirkung von 3.15 (für Traceroute):** Mit UTF-8 als Standard dekodiert `subprocess.run(..., text=True)` die Ausgabe als UTF-8. PEP 686 empfiehlt ausdrücklich, `text=True` durch `encoding="utf-8"` oder `encoding="locale"` zu ersetzen [Q3]. `tracert` auf deutschem Windows gibt seine Kopfzeile nicht in UTF-8 aus. Deshalb liest RootPing die Ausgabe als Bytes und dekodiert selbst mit `errors="replace"` (Abschnitt 3.11). Die ruff-Regel `PLW1514` (Kodierung nicht angegeben) erzwingt explizite Kodierungen im ganzen Code.

**Verworfen**
- *Bei 3.12 bleiben:* nur noch Sicherheitsupdates [Q1], kein Vorteil.
- *Nur 3.15 (Untergrenze = 3.15):* noch einfacher (eine Version, eine CI-Achse), aber 3.15 ist 7 Wochen alt. Mit 3.14 als Untergrenze fällt auf, falls 3.15-spezifisches Verhalten (z. B. die Kodierung) unbeabsichtigt genutzt wird. Ist als Alternative in Abschnitt 5 aufgeführt.
- *Free-threaded Python (ohne GIL):* offiziell unterstützt seit 3.14 (PEP 779) [Q5], bringt RootPing aber nichts, weil die Arbeit I/O-gebunden ist und in asyncio läuft.

**Unsicher:** 3.15.x ist jung. Falls in 3.15.x ein Fehler auftaucht, der RootPing trifft, bleibt 3.14 als getestete Rückfallebene.

### 3.2 Paketverwaltung: uv ✅ ➕

**Empfehlung:** **uv 0.13.x**, Lockfile `uv.lock` im Repo, in CI `uv sync --locked`, und **Cooldown** `exclude-newer = "7 days"` in `pyproject.toml`.

**Begründung**
- uv ist der Plan und bleibt die beste Wahl: ein Werkzeug für Python-Installation, virtuelle Umgebung, Abhängigkeiten, Lockfile, Build und Werkzeug-Installation, auf Windows und Linux gleich.
- Das Lockfile enthält Hashes; uv prüft heruntergeladene Pakete dagegen [Q29]. Im Test enthielt das Lockfile 328 Hash-Einträge für 59 Pakete (T9).
- **Cooldown:** `exclude-newer = "7 days"` ignoriert Paketversionen, die jünger als 7 Tage sind. Das schützt vor kompromittierten Releases, die meist innerhalb weniger Tage entdeckt werden [Q29]. **Im Test bestätigt** (T9): mit Cooldown wurde `anthropic>=2.14` abgelehnt, weil 2.11–2.14 alle in den letzten 7 Tagen erschienen waren.
- **Praktische Lehre aus T9:** `uv add` schreibt als Untergrenze die *neueste* Version (z. B. `>=4.14.8`), die mit Cooldown dann nicht auflösbar ist. Deshalb: **Cooldown vor dem ersten `uv add` setzen** und Untergrenzen auf getestete Minor-Versionen legen; das Lockfile legt die genaue Version fest.

**Verworfen**
- *Poetry, PDM, Hatch, pip + venv:* funktionieren, aber uv deckt alles ab, ist schneller und der heutige Standard für neue Projekte; ein Wechsel brächte nur Komplexität.
- *pip-tools:* braucht zusätzlich ein Werkzeug für Python-Versionen und Umgebungen.

**Unsicher:** `uv audit` (Abgleich mit Sicherheitsdatenbank OSV) existiert, ist aber laut uv selbst **experimentell** (T9). Deshalb nicht als verbindlicher CI-Schritt, sondern optional; verbindlich sind Dependabot-Sicherheitswarnungen (3.22).

### 3.3 Projektlayout ➕

**Empfehlung:** **src-Layout** (`src/rootping/…`), Build-Backend **`uv_build`**, Einstiegspunkt über `[project.scripts] rootping = "rootping.cli:app"`.

**Begründung**
- `uv init --package` erzeugt genau dieses Layout mit `uv_build` als Backend (T1). Das src-Layout verhindert, dass Tests aus Versehen den Quellordner statt des installierten Pakets importieren, und ist der Standard der Python Packaging Authority.
- Vorgeschlagene Struktur (an Abschnitt 4 von [projektplan.md](projektplan.md) angelehnt):

```
src/rootping/
  cli.py              # Typer-App: run, status, diagnose, trace, mcp
  config.py           # Einstellungen (pydantic-settings)
  probes/             # Probe-Basisklasse, PROBES-Liste, ping.py, dns.py
  net/                # icmp.py (Ping-Backends), traceroute.py
  platform/           # linux.py, windows.py (Gateway, Ping-Backend)
  storage/            # einziger DB-Zugriff + migrations/*.sql
  detect/             # Auffälligkeit, Störung (Hysterese)
  diagnose/           # rules.py (Entscheidungsbaum), agent.py (Claude)
  tools.py            # gemeinsamer Werkzeugsatz für Agent und MCP
  mcp_server.py       # dünne MCP-Hülle um tools.py
tests/
docs/
```

**Verworfen:** *Flaches Layout* (`rootping/` im Wurzelordner): einfacher, aber anfällig für Import-Verwechslungen in Tests. *Hatchling/setuptools* als Backend: funktionieren, aber `uv_build` braucht keine Zusatzkonfiguration.

### 3.4 Linting und Formatierung: ruff ✅ ➕

**Empfehlung:** **ruff** als Linter und Formatierer. Zusätzlich zu den üblichen Regeln diese, weil sie genau RootPing-Risiken und Kais Grundregeln abdecken (alle Regelnamen mit `ruff rule` geprüft, T10):

| Regel(n) | Prüft | Warum für RootPing |
|---|---|---|
| `D` + `pydocstyle.convention = "google"`, inkl. `D417` | Fehlende Docstrings, undokumentierte Parameter | **Erzwingt „kein Code ohne Doku“ automatisch in CI** (T10: fehlende Modul- und Funktions-Docstrings werden gemeldet) |
| `ASYNC` (z. B. `ASYNC230`) | Blockierende Aufrufe in `async`-Funktionen | Ein blockierender Aufruf hält alle Messungen an |
| `RUF006` | Tasks ohne gespeicherte Referenz | Vergessene Tasks verschwinden still |
| `DTZ` (z. B. `DTZ005`) | `datetime.now()` ohne Zeitzone | Datenmodell schreibt UTC vor |
| `T201` | `print()` | Ein `print` im MCP-Server zerstört das Protokoll (3.15/3.19) |
| `PLW1514` | `open()`/Text ohne Kodierung | Windows/Linux- und 3.14/3.15-Unterschiede (3.1) |
| `S603`/`S607` | Unterprozess-Aufrufe | Traceroute ist der einzige erlaubte Unterprozess; bewusst freigeben |

**Verworfen:** *Black + isort + flake8 + pydocstyle* einzeln: dasselbe Ergebnis mit vier Werkzeugen statt einem.

### 3.5 Typprüfung ➕ ❓

**Empfehlung:** **Pyright** im Modus `standard` als verbindliche Prüfung in CI, installiert als Dev-Abhängigkeit `pyright[nodejs]` (bringt Node.js als Wheel mit, damit unter Windows kein separates Node nötig ist; das Extra `nodejs` → `nodejs-wheel-binaries` ist in den Paketmetadaten von pyright 1.1.414 aufgeführt [Q8]). **ty** (von Astral, den uv/ruff-Machern) beobachten und wechseln, sobald es stabil ist.

**Begründung**
- Pyright ist ausgereift, sehr schnell und dieselbe Engine wie Pylance in VS Code. In einem Vergleich vom April/Mai 2026 lag Pyright bei der Konformität mit der Typing-Spezifikation bei 97,8 %, mypy bei 58,3 %, ty bei 53,2 % (Sekundärquelle) [Q31].
- ty ist laut Astral-naher Doku **noch Beta**, mit Ziel „stabil 1.0 im Jahr 2026“ [Q32]; die aktuelle Version ist **0.0.111** vom 25.11.2026 [Q8], also noch kein 1.0. Für ein Projekt, dessen Gerüst „absolut solide“ sein soll, ist ein Beta-Werkzeug als verbindliche Prüfung die falsche Wahl.
- Beide fanden im Test denselben absichtlich eingebauten Typfehler (T10), unterstützen Python 3.15 (T10).

**Verworfen**
- *mypy* (2.4.1): funktioniert, aber geringere Konformität [Q31] und langsamer; kein Grund, es neu einzuführen.
- *Pyrefly* (Meta, 1.5.0) und *basedpyright*: brauchbar, aber weniger verbreitet; beim Erklären im Bewerbungsgespräch ist „Pyright, dieselbe Engine wie in VS Code“ eingängiger.

**Unsicher:** Die Konformitätszahlen sind von März 2026 und aus einem Blog [Q31]. ty entwickelt sich schnell; in einem halben Jahr kann die Empfehlung anders ausfallen. Deshalb ist der Wechsel als offene Entscheidung (Abschnitt 5) festgehalten.

### 3.6 Git-Hooks: prek ➕

**Empfehlung:** **prek** (0.5.x) mit einer normalen `.pre-commit-config.yaml`, die ruff (check + format) und Pyright ausführt.

**Begründung:** prek ist ein in Rust geschriebener Ersatz für pre-commit, eine einzelne Datei ohne Laufzeit-Abhängigkeiten, **vollständig kompatibel mit `.pre-commit-config.yaml`** [Q33]. Laut Projektseite nutzen es u. a. CPython, Apache Airflow, FastAPI, Ruff und Home Assistant [Q33]. Es gibt Wheels für Windows (x64 und ARM64) [Q8]. Weil das Konfigurationsformat identisch ist, kostet ein Wechsel zurück zu pre-commit nichts.

**Verworfen:** *pre-commit* (4.7): ausgereift und genauso gut, braucht aber eine eigene Python-Umgebung. *Keine Hooks:* CI fängt alles, aber später; Hooks sparen Runden.

**Unsicher:** prek selbst sagt „prek is pretty new“ [Q33]. Risiko gering, weil die Konfiguration mit pre-commit austauschbar ist.

### 3.7 Nebenläufigkeit und Scheduler ✅

**Empfehlung:** **asyncio** (Standardbibliothek) mit `asyncio.TaskGroup` (strukturierte Nebenläufigkeit: ein Fehler beendet die Gruppe sauber) und `asyncio.timeout()` (seit 3.11). Ein **eigener kleiner Scheduler** (eine `async`-Funktion pro Probe, driftfreier Takt über `loop.time()`), kein Scheduler-Framework.

**Begründung**
- Alle Netzwerkaufrufe sind I/O-gebunden; asyncio ist dafür gemacht, und die Bibliotheken (`dnspython`, `anthropic`, `mcp`) sind async-fähig.
- Der Scheduler braucht nur „alle N Sekunden, ohne Drift, mit Timeout und Fehlerfang“. Das sind etwa 40 Zeilen eigener, vollständig erklärbarer Code. T3 zeigt das Muster (fester Takt mit `TaskGroup`).
- **Windows-Details, die das Design berücksichtigen muss:**
  - Unter Windows ist der `ProactorEventLoop` Standard [Q7]; er unterstützt Unterprozesse (für Traceroute) [Q7]. `dnspython` behandelt Windows im asyncio-Backend ausdrücklich (`_asyncio_backend.py`, `_is_win32`) [Q8, Quellcode 2.9.2].
  - Die Auflösung der Zeitgeber unter Windows ist laut Python-Doku „usually around 15.6 milliseconds“ [Q7]. Das betrifft nur den **Sendezeitpunkt** der Pings (bis ~16 ms ungenau), **nicht die gemessene Laufzeit**, die das Betriebssystem misst (3.8).
  - **Ruhezustand erkennen:** `time.monotonic()` verhält sich je System unterschiedlich: unter Linux bleibt `CLOCK_MONOTONIC` im Suspend stehen [Q6]; unter Windows nutzt Python seit 3.13 `QueryPerformanceCounter` [Q4]. Ob dieser Zähler den Ruhezustand mitzählt, habe ich nicht verlässlich belegen können. Deshalb erkennt RootPing Messlücken über die **Wanduhr-Differenz** (`time.time()`) zwischen zwei Runden und nutzt `monotonic` nur für den Takt.

**Verworfen**
- *APScheduler:* die stabile Reihe ist 3.11.x; 4.0 ist seit Jahren im Alpha-Stadium (zuletzt 4.0.0a6) [Q8]. Für „alle 10 s“ unnötig.
- *anyio/trio:* anyio steckt ohnehin in `anthropic` und `mcp` [Q8], aber für eigenen Code bringt es keinen Vorteil, der eine zweite Begriffswelt rechtfertigt.
- *Threads:* mehr Fehlerquellen (gleichzeitige DB-Zugriffe), schwerer zu erklären. Einzige Ausnahme: der blockierende Windows-ICMP-Aufruf läuft über `asyncio.to_thread` (3.8).

### 3.8 Ping 🔁 ❓

**Empfehlung:** Ein eigenes, kleines Modul `rootping/net/icmp.py` mit **einer** Funktion pro Betriebssystem:

```text
async def echo(target: str, timeout: float) -> float | None
    # Ein einzelnes ICMP-Echo. Rückgabe: Laufzeit in ms oder None (verloren).
```

| | Linux | Windows |
|---|---|---|
| Mechanismus | ICMP-Datagram-Socket (`SOCK_DGRAM`, kernel-seitig, ohne Root) | Windows-ICMP-API `IcmpSendEcho2` aus `Iphlpapi.dll`, derselbe Weg wie `ping.exe` |
| Umsetzung | `icmplib` (`async_ping(count=1, privileged=False)`), getestet in T2/T3 | `ctypes` (Standardbibliothek), blockierender Aufruf über `asyncio.to_thread` |
| Rechte | `net.ipv4.ping_group_range` muss die Gruppe erlauben (B3) | keine besonderen Rechte nötig [Q11][Q13] |
| Auflösung | Gleitkomma-Millisekunden | **ganze Millisekunden** (`RoundTripTime` ist `ULONG`, „in milliseconds“ [Q12]); Werte unter 1 ms erscheinen als 0, wie „<1ms“ bei `ping.exe` |

Darüber liegt ein **Takt-Treiber**: Pro Ziel startet er jede Sekunde ein `echo()` (ohne auf die Antwort zu warten), sammelt die Ergebnisse einer 10-s-Runde nach **Sendezeitpunkt** und berechnet daraus selbst: Mittelwert, Maximum, Verlust in %, Jitter. Die Berechnung ist eine reine Funktion `summarize(rtts: list[float | None]) -> Summary`, ohne Netzwerk testbar (mit Hypothesis, 3.16).

**Begründung**
- **B1:** Der Windows-Weg über `icmplib` braucht Admin. Die ICMP-API braucht keinen. Damit läuft RootPing unter Windows wie `ping.exe`: ohne Admin, ohne Unterprozess, ohne sprachabhängige Textausgabe.
- **B2:** Der feste Takt hält „1 Ping pro Sekunde“ auch bei Verlust ein (T3: 6,0 s statt 14,0 s für 5 Pakete).
- **Jitter selbst definieren:** `icmplib` berechnet Jitter als Mittel der absoluten Differenzen aufeinanderfolgender Laufzeiten (models.py, `jitter`) [Q9]. Wenn RootPing das selbst berechnet, ist die Definition dokumentiert, auf beiden Systemen identisch und unabhängig von einer Bibliothek. Vorschlag: genau diese Definition beibehalten (verständlich, entspricht der Idee von RFC 3550), verlorene Pakete werden übersprungen.
- **Einfach erklärbar:** „Unter Linux nutze ich den Ping-Socket des Kernels, unter Windows dieselbe API wie `ping.exe`. Beides ohne Adminrechte.“
- `icmplib` bleibt unter Linux sinnvoll: klein, reines Python, MIT-Lizenz, und der Linux-Pfad nutzt eine stabile Kernel-Schnittstelle. **Aber:** das letzte Release ist 3.0.4 vom **10.10.2023** [Q8]. Weil RootPing nur noch einen einzigen Aufruf (`async_ping(count=1)`) nutzt, wäre ein Ersatz durch ~60 Zeilen eigenen Socket-Code jederzeit möglich, ohne dass sich außerhalb von `icmp.py` etwas ändert.

**Verworfen**
- *`icmplib` überall:* scheitert unter Windows ohne Admin (B1).
- *System-`ping` aufrufen (bisheriger Plan B):* ein neuer Prozess pro Echo, bei 1 Ping/s und 3–4 Zielen also 3–4 Prozessstarts pro Sekunde; Ausgabe je nach Sprache verschieden. Bleibt als **Notlösung** dokumentiert, falls die ICMP-API wider Erwarten scheitert.
- *`ping3`* (5.1.6, gepflegt): nutzt ebenfalls Raw bzw. Datagram Sockets, also dasselbe Windows-Problem; zudem synchron.
- *`ipscout`* (2.5.4): macht genau das Richtige (Linux-Ping-Socket, Windows über `iphlpapi.dll`, „Nothing needs elevation“) [Q18], ist aber erst seit **29.07.2026** auf PyPI, hat 19 Releases in 4 Monaten und einen einzelnen Maintainer [Q8]. Für den Kern des Projekts ist das ein zu hohes Lieferketten-Risiko, und eigener Code (~80 Zeilen) ist für das Bewerbungsgespräch wertvoller.
- *`winping`* (0.2.4): nutzt die Windows-ICMP-API, letztes Release **2019**, kein asyncio [Q8][Q19].
- *TCP-Verbindungszeit statt ICMP:* misst etwas anderes, und Router haben oft keinen offenen Port (wie schon in ADR-004).

**Unsicher**
- Die Windows-Umsetzung ist **nicht selbst getestet** (kein Windows-Rechner). Microsoft-Doku [Q11][Q12] und das Verhalten von `ping.exe` sind eindeutig; trotzdem bleibt der Spike am Anfang von Sprint 1, jetzt mit klarer Erwartung. Er muss auf Kais PC **ohne erhöhte Rechte** laufen, weil GitHub-Windows-Runner als Administrator laufen [Q37] und dort auch der falsche Weg funktionieren würde.
- `IcmpSendEcho2` kann auch asynchron über ein Windows-Event arbeiten [Q11]. `asyncio.to_thread` ist einfacher; bei 3–4 Zielen und ≤ 2 s Timeout sind höchstens ~8 Threads gleichzeitig beschäftigt. Sollte das nicht reichen, ist der Event-Weg die Ausbaustufe.
- IPv6 ist in v1 nicht vorgesehen (wie bisher implizit). Die Windows-API hat dafür eigene Funktionen (`Icmp6SendEcho2`) [Q11].

### 3.9 Gateway-Erkennung 🔁

**Empfehlung:** Ohne Unterprozess. **Linux:** `/proc/net/route` lesen (Zeile mit Ziel `00000000` = Standardroute). **Windows:** `GetBestRoute` aus `Iphlpapi.dll` über `ctypes`, mit einer öffentlichen Zieladresse; das Feld `dwForwardNextHop` ist der Router, `dwForwardIfIndex` das Interface [Q17].

**Begründung:** Der Scheduler prüft den Netzwerk-Kontext **vor jeder Runde** ([probes.md](probes.md)). Ein PowerShell-Aufruf (`Get-NetRoute`) alle 10 s wäre teuer (Start von PowerShell). `route print` liefert sprachabhängigen Text. `GetBestRoute` ist eine kleine, seit Windows 2000 verfügbare Funktion mit fester Struktur [Q17] und ohne besondere Rechte (die Doku nennt keine). Damit nutzt `platform/windows.py` für Ping und Gateway dieselbe DLL.

**Verworfen:** *`netifaces`* (letztes Release 2021) [Q8], *`netifaces-plus`/`netifaces2`* (wenig verbreitet), *`psutil`* (liefert kein Gateway), *`pyroute2`* (nur Linux) [Q8].

**Unsicher:** `GetBestRoute` ist IPv4-only (laut Signatur; die Doku sagt es nicht ausdrücklich) [Q17]. Für v1 passend. Nicht selbst unter Windows getestet.

### 3.10 DNS: dnspython ✅ ➕

**Empfehlung:** **dnspython 2.9** mit `dns.asyncresolver`, pro Messung ein Resolver mit genau **einem** fest gesetzten Nameserver, Timeout aus der Konfiguration, Fehlerarten (`Timeout`, `NXDOMAIN`, `NoAnswer`, `SERVFAIL` über `NoNameservers`) auf die Werte in [datenmodell.md](datenmodell.md) abgebildet.

**Begründung**
- Kein anderes Python-Paket liefert die DNS-Fehlerarten so präzise; asyncio-fähig; liest unter Windows die System-DNS-Server aus der Registry (optional über WMI) (`win32util.py`) [Quellcode 2.9.2].
- Aktuell gepflegt (2.9.2 vom 03.11.2026) [Q8].

**Zwei fachliche Hinweise (betreffen [diagnose.md](diagnose.md), nicht die Bibliothek):**
1. **„system“ ist unter Linux oft nicht der Router:** Mit systemd-resolved zeigt `/etc/resolv.conf` auf den lokalen Stub `127.0.0.53`; die echten Server stehen in `/run/systemd/resolve/resolv.conf` [Q44]. RootPing würde sonst den lokalen Cache messen. Vorschlag: zusätzliches Ziel `"gateway"` (DNS-Anfrage direkt an die Router-IP, die meisten Heimrouter sind DNS-Weiterleiter) und für „system“ die tatsächlich verwendete Server-IP mitspeichern.
2. **Cache-Effekt:** Wer alle 30 s `example.com` abfragt, misst ab der zweiten Anfrage meist den Cache des Routers bzw. Resolvers, nicht die Auflösung beim Provider. Das ist eine Entscheidung für die Diagnose, keine Technikfrage; ich nenne sie hier nur, damit sie nicht untergeht.

**Verworfen:** *`socket.getaddrinfo`* (keine Fehlerarten, kein Server wählbar), *`aiodns`/c-ares* (C-Abhängigkeit, kein Mehrwert).

### 3.11 Traceroute ✅ ➕

**Empfehlung:** Wie in [ADR-005](adr/005-traceroute-auf-anfrage.md): System-Befehl (`tracert -d` / `traceroute -n` / `tracepath -n`) über `asyncio.create_subprocess_exec` (nie `shell=True`). **Neu:** Ausgabe als **Bytes** lesen und mit `errors="replace"` dekodieren; ausgewertet werden nur IP-Adressen, Zahlen und `*`.

**Begründung:** Ab Python 3.15 ist UTF-8 die Standard-Kodierung [Q3]; `tracert` auf deutschem Windows schreibt seine Kopfzeilen (z. B. mit „über“) nicht in UTF-8. Mit `text=True` drohen dann Dekodierfehler oder Zeichensalat. Weil nur ASCII-Teile (IPs, Zahlen) ausgewertet werden, ist „Bytes + `errors="replace"`“ robust auf beiden Systemen und beiden Python-Versionen. Mit `-d`/`-n` gibt es keine Rückwärts-DNS-Namen, was auch die Angriffsfläche für eingeschleuste Texte im KI-Prompt klein hält (3.22).

**Verworfen:** *Eigenes Traceroute über ICMP mit steigender TTL:* bräuchte unter Windows `IcmpSendEcho2` mit TTL-Optionen (möglich, aber mehr Code) und unter Linux Raw Sockets bzw. Spezialoptionen; für ein Werkzeug, das selten läuft, nicht gerechtfertigt.

### 3.12 SQLite und Migrationen ✅ ➕

**Empfehlung:** **`sqlite3` aus der Standardbibliothek**, Zugriff nur über `storage` (wie geplant), dazu:

| Maßnahme | Warum | Beleg |
|---|---|---|
| `PRAGMA journal_mode=WAL` | Messdienst schreibt, MCP-Server und CLI lesen gleichzeitig, ohne sich zu blockieren | T5, T6 |
| `PRAGMA synchronous=NORMAL` (mit WAL) | Schnelle Commits; bei Stromausfall gehen höchstens die letzten Sekunden verloren, die DB bleibt konsistent | T6: Median 0,01 ms vs. 0,28 ms bei `FULL` (Linux-Container) |
| `PRAGMA foreign_keys=ON`, `busy_timeout=5000` | Fremdschlüssel sind in SQLite sonst aus; kurze Sperren abwarten statt Fehler | T5 |
| **`STRICT`-Tabellen** | SQLite prüft Spaltentypen; ein Text in einer `REAL`-Spalte wird abgelehnt statt still gespeichert | T5 (`cannot store TEXT value in REAL column`) |
| `CHECK (json_valid(details))` für JSON-Spalten | Kaputtes JSON kommt gar nicht erst in die DB | T5 |
| MCP-Server öffnet die DB **nur lesend** (`file:…?mode=ro`, `uri=True`) | Werkzeuge der KI können nichts verändern | T6 (`attempt to write a readonly database`) |
| Zeitstempel als ISO-8601-Text in UTC, selbst formatiert | Der eingebaute datetime-Adapter ist **seit 3.12 veraltet** | T5 (`DeprecationWarning … deprecated as of Python 3.12`) |
| Migrationen: nummerierte `.sql`-Dateien + `PRAGMA user_version` (wie geplant) | ~30 Zeilen eigener Code, vollständig erklärbar | T5 |
| Verbindung mit `autocommit=False` (PEP-249-Verhalten, seit 3.12); **PRAGMAs vorher** im Autocommit-Modus setzen | Mit offener Transaktion schlägt `journal_mode=WAL` fehl | T5 (erster Versuch: `cannot change into wal mode from within a transaction`) |

- Die mit Python 3.15.2 gebündelte SQLite-Version war **3.54.1** (T1); `STRICT` braucht ≥ 3.37, JSON-Funktionen sind seit 3.38 fest eingebaut.
- **Synchron im Event-Loop schreiben** (ein Commit pro Runde, alle 10 s wenige Zeilen) ist bei diesen Zeiten vertretbar und am einfachsten. Unter Windows (NTFS, Virenscanner) können Commits langsamer sein; nicht gemessen. Vorschlag: Dauer jedes Commits loggen und ab 50 ms warnen; falls nötig auf einen eigenen Schreib-Thread umstellen (das betrifft nur `storage`).

**Verworfen**
- *`aiosqlite`* (0.22.1): ist im Kern ein Thread um `sqlite3`; bei diesen Datenmengen ohne Nutzen, eine Abhängigkeit mehr.
- *SQLAlchemy + Alembic:* mächtig, aber für sieben Tabellen und ein Gerät ein großes zusätzliches Konzept. Der Wechsel wäre später auf `storage` begrenzt.
- *`yoyo-migrations`* (letztes Release 08/2024) [Q8]: unnötig gegenüber 30 Zeilen eigenem Code.
- *SQLModel/Pydantic-ORM:* vermischt Validierung und Speicherung; widerspricht „nur `storage` kennt die DB“.

### 3.13 Konfiguration und Validierung ✅ ➕

**Empfehlung:** TOML-Datei wie geplant, eingelesen und **validiert mit pydantic-settings** (2.16). Jede Probe bekommt ein eigenes kleines Pydantic-Modell für ihren Abschnitt `[probes.<name>]`; Umgebungsvariablen mit Präfix `ROOTPING_` überschreiben Werte (praktisch für das Labor und CI). Der Anthropic-API-Schlüssel steht **nie** in der TOML-Datei, sondern kommt aus `ANTHROPIC_API_KEY`, die das SDK selbst liest.

**Begründung**
- Getestet (T8): TOML-Quelle über `TomlConfigSettingsSource`, verschachtelte Umgebungsvariable `ROOTPING_THRESHOLDS__LATENCY_MS_INTERNET=45` überschreibt die Datei, ein falscher Wert (`abc`) ergibt eine klare Fehlermeldung mit Pfad (`thresholds.latency_ms_internet … Input should be a valid number`).
- Pydantic ist ohnehin schon da: `anthropic`, `mcp` und seit 0.29 auch **Typer** hängen davon ab [Q8][Q35].
- **Folge für [probes.md](probes.md):** `Probe.__init__(self, settings: dict)` wird zu einem typisierten Einstellungsobjekt. Tippfehler in der Konfiguration (`intervall = 10`) fallen beim Start auf (`extra="forbid"`), nicht erst zur Laufzeit.

**Verworfen:** *Nur `tomllib` + `dict`:* keine Validierung, Fehler erst zur Laufzeit. *`dynaconf`, `hydra`:* deutlich mehr Konzept als nötig. *YAML:* zusätzliche Abhängigkeit, TOML ist in Python eingebaut.

### 3.14 CLI: Typer ✅

**Empfehlung:** **Typer 0.29**, mit Obergrenze der Minor-Version in `pyproject.toml` (`typer>=0.29,<0.30`).

**Begründung:** Kai hat Typer gewählt, es ist sehr verbreitet (FastAPI-Familie) und leicht lesbar. Zwei Neuerungen 2026, die man kennen sollte [Q35]: Seit **0.26.0 (26.05.2026)** bringt Typer Click als eigenen Quellcode mit, statt davon abzuhängen; seit **0.29.0 (09.11.2026)** nutzt Typer Pydantic zur Parameterprüfung. Typer ist weiterhin 0.x und hatte in diesem Jahr mehrere Releases mit „Breaking Changes“; deshalb die Obergrenze, das Lockfile hält die genaue Version fest.

**Verworfen:** *Cyclopts* (5.5, semantisch versioniert): technisch sehr gut und eine echte Alternative, aber weniger bekannt; kein Grund, Kais Wahl umzuwerfen. *argparse:* viel Handarbeit. *Click direkt:* mehr Boilerplate als Typer.

### 3.15 Logging ➕

**Empfehlung:** **stdlib `logging`**, eine zentrale Funktion `setup_logging()`. Konsole: kurz und lesbar (Typer bringt `rich` schon mit [Q8]). Datei: im Log-Ordner von `platformdirs`, **eine Datei pro Prozess** (`run.log`, `mcp.log`), mit Rotation.

**Begründung**
- Der **MCP-Server über stdio darf auf stdout nichts außer MCP-Nachrichten schreiben** („MUST NOT“), Logs gehen nach stderr [Q22]. Ein einziges `print()` im falschen Moment zerstört die Verbindung zu Claude Desktop/Code. Deshalb: ruff-Regel `T201` (kein `print`) und Logging im MCP-Prozess nur nach stderr bzw. in die Datei.
- **Eine Datei pro Prozess**, weil `RotatingFileHandler` unter Windows beim Umbenennen scheitert, wenn ein anderer Prozess dieselbe Datei offen hat (Freigabeverletzung, Windows-Fehler 32) [Q43]. Messdienst und MCP-Server laufen als getrennte Prozesse.

**Verworfen:** *structlog* (26.1) und *loguru* (0.8): gut, aber ein zusätzliches Konzept für ein Programm mit einer Handvoll Log-Stellen. JSON-Logs braucht RootPing nicht; die strukturierten Daten stehen in SQLite.

### 3.16 Tests ✅ ➕

**Empfehlung:** **pytest 9.2**, **pytest-asyncio 1.5**, **Hypothesis** für die reinen Rechenfunktionen, `coverage` über `pytest-cov`.

**Begründung**
- pytest-asyncio 1.0 (26.05.2025) hat die alte `event_loop`-Fixture entfernt; 1.4.1 hat Python 3.15 offiziell aufgenommen [Q36]. Viele Anleitungen im Netz zeigen noch den alten Stil; im Projekt nur den neuen verwenden.
- **Hypothesis** (eigenschaftsbasiertes Testen) passt genau zu zwei Stellen, die sonst schwer vollständig zu testen sind: `summarize()` (z. B. „Verlust ist immer zwischen 0 und 100 %“, „Maximum ≥ Mittelwert“, „alles verloren ⇒ Verlust 100 %“) und die **Störungserkennung mit Hysterese** (z. B. „eine Störung wird nie in derselben Runde geöffnet und geschlossen“). Das ist im Bewerbungsgespräch ein gutes Beispiel für durchdachtes Testen, ohne viel Aufwand.
- Wie in [probes.md](probes.md) geplant: Netzwerk in Unit-Tests immer ersetzen (`FakeProbe`, gefälschtes `echo()`).

**Verworfen:** *pytest-xdist* (parallele Tests): bei dieser Testmenge unnötig. *Snapshot-Bibliotheken* (syrupy, inline-snapshot): für die Traceroute-Beispielausgaben reichen normale Fixture-Dateien.

### 3.17 CI ✅ ➕

**Empfehlung:** GitHub Actions mit Matrix **`windows-latest` und `ubuntu-latest` × Python 3.14 und 3.15**, Schritte: `astral-sh/setup-uv` → `uv sync --locked` → ruff check + format --check → Pyright → pytest. Das Störungslabor (Docker + netem) läuft nur auf Linux in einem eigenen Job.

**Begründung und Fakten**
- `ubuntu-latest` wird zwischen **19.10. und 19.11.2026** von Ubuntu 24.04 auf **26.04** umgestellt [Q38]; `windows-latest` ist Windows Server 2025, seit Juni 2026 mit Visual Studio 2026 [Q39]. Für reproduzierbare Läufe kann man feste Labels (`ubuntu-24.04`, `windows-2025`) nehmen; Vorschlag: `-latest` für die normale Matrix, weil RootPing keine Systempakete braucht.
- Standard-Runner für **private** Repos: 2 CPU, 8 GB RAM; für öffentliche 4 CPU, 16 GB [Q37].
- **Wichtig für Windows-Tests:** Die Runner laufen **als Administrator mit abgeschalteter UAC** [Q37]. Ein Test, der „ohne Admin“ beweisen soll, ist dort nicht aussagekräftig (siehe 3.8).
- `permissions: contents: read` als Standard in jedem Workflow (3.22).

### 3.18 Doku-Werkzeuge ✅

**Empfehlung:** Wie bisher **Markdown im Repo** mit **Mermaid**-Diagrammen (GitHub stellt beides direkt dar). Docstrings im **Google-Stil**, erzwungen durch ruff (`D`, 3.4). **Keine Doku-Website in v1.**

**Begründung:** Für ein Bewerbungsprojekt liest man README und `docs/` direkt auf GitHub. Eine Website kostet Pflege ohne Mehrwert.

**Falls später eine Website gewünscht ist:** nicht mehr MkDocs. MkDocs 1.x hatte rund 18 Monate kein Release, das Repo ist seit 02.10.2026 für externe Issues/PRs geschlossen, MkDocs 2.0 ist inkompatibel mit Material und Plugins; das Material-Team empfiehlt seinen Nachfolger **Zensical** und hat Material nur noch bis **05.05.2027** in kritischer Wartung [Q34]. Zensical ist jung (0.1.3) [Q8].

### 3.19 MCP ✅ 🔁

**Empfehlung:** **MCP Python SDK 2.x** (`mcp>=2.3,<3`), Server-Klasse **`MCPServer`**, Transport **nur stdio**, Werkzeuge als dünne Hülle um `tools.py` (gleiche Funktionen wie für den Agenten), Rückgabetypen als Pydantic-Modelle (ergibt automatisch ein Ausgabe-Schema), Datenbank nur lesend.

**Was sich seit dem Planentwurf geändert hat**
- **SDK 2.0.0 ist seit 28.07.2026 stabil**; 1.x ist im Wartungsmodus (nur noch Sicherheits- bzw. kritische Fehlerkorrekturen) [Q21]. Aktuell ist 2.3.0 vom 02.10.2026 [Q8].
- **`FastMCP` heißt jetzt `MCPServer`**, Import `from mcp.server.mcpserver import MCPServer`; der alte Pfad `mcp.server.fastmcp` wirft `ModuleNotFoundError` [Q20]. Kontext wird per Parameter `ctx: Context` übergeben; synchrone Handler laufen in einem Worker-Thread [Q20].
- **Attributnamen sind jetzt snake_case** (`output_schema`, `structured_content`, `protocol_version`). Im eigenen Test (T4) schlugen die alten camelCase-Namen mit `AttributeError` fehl. **Viele Tutorials und KI-Antworten zeigen noch den 1.x-Stil.**
- Neue Spezifikation **2026-07-28** (zustandslos, `server/discover` statt `initialize`-Handshake) [Q22][Q20]. Im Test handelte der Client noch **2025-11-25** aus (T4), passend zur Migrationsanleitung (Handshake kann 2026-07-28 nicht aushandeln, dafür gibt es `LATEST_HANDSHAKE_VERSION`) [Q20]. Für RootPing spielt das keine Rolle; das SDK spricht beide.

**Begründung:** T4 zeigt den kompletten Weg: Server mit `@mcp.tool()` und Pydantic-Rückgabe, Client listet das Werkzeug mit Beschreibung (aus dem Docstring) und Ausgabe-Schema, Aufruf liefert strukturierte Daten. Das ist genau das Muster für RootPing.

**Sicherheit:** Nur stdio (kein offener Netzwerk-Port), DB nur lesend (T6), aktive Werkzeuge (`ping_now`, `traceroute_now`) prüfen ihre Eingaben (nur einzelne Hosts, keine Adressbereiche) und haben das Rate-Limit aus [ADR-005](adr/005-traceroute-auf-anfrage.md).

**Verworfen**
- *FastMCP (eigenständiges Paket, 4.2)*: das eigenständige Projekt hat mehr Funktionen (u. a. für Hosting), aber RootPing braucht nur einen lokalen stdio-Server. Das offizielle SDK ist die neutralere Wahl und Kais ursprüngliche Entscheidung.
- *Streamable HTTP als Transport:* öffnet einen Port, braucht Authentifizierung; für lokale Nutzung mit Claude Desktop/Code unnötig.
- *Agent spricht über MCP mit dem eigenen Server* (das Anthropic-SDK hat dafür Helfer, `anthropic.lib.tools.mcp`, T7): elegant („garantiert dieselben Werkzeuge“), aber ein zusätzlicher Prozess und eine Beta-Schnittstelle. Direkter Funktionsaufruf über `tools.py` erreicht dasselbe Ziel einfacher.

### 3.20 Anthropic SDK und Agent-Ansatz ✅ ❓

**Empfehlung:** **`anthropic` 2.x** (aktuell 2.14.0), **Messages API mit einer eigenen, kleinen Agent-Schleife** (`while stop_reason == "tool_use"`), Werkzeuge aus `tools.py`, Endergebnis als **strukturierte Ausgabe** (`output_config.format` mit JSON-Schema aus einem Pydantic-Modell `Diagnosis`). Modell, Effort, maximale Werkzeugaufrufe und Tageslimit kommen aus der Konfiguration.

**Was sich seit dem Planentwurf geändert hat**
- **SDK 2.0** sendet die neue API-Version **2026-10-21** [Q24]. Dabei sind u. a. `temperature`, `top_p` und `top_k` **entfernt**: eine Anfrage damit gibt einen 400-Fehler [Q24]; im SDK 2.14 sind die Parameter nicht mehr in der Signatur (T7). Seit SDK 1.x nutzt das SDK `httpx2` statt `httpx` [Q23]. Python ≥ 3.10 [Q8].
- **Folge für die Auswertung (wichtig):** Es gibt keine `temperature=0` mehr für „möglichst gleiche Antworten“. Die Auswertung muss deshalb **mehrere Durchläufe pro Szenario** machen (das ist mit 3 Läufen pro Szenario in [diagnose.md](diagnose.md) schon angelegt) und **Streuung** angeben, nicht nur einen Wert. Modell-ID und SDK-Version gehören in jede Diagnose (Spalte `model` existiert schon).
- Auf **Claude Opus 5.5** (laut Modellübersicht von Anthropic das empfohlene Einstiegsmodell [Q45]) gibt `tool_choice` mit `any`/`tool` einen Fehler; die Preistabelle führt dafür keinen Wert mehr [Q25]. „Zwinge das Modell, das Werkzeug `submit_diagnosis` aufzurufen“ geht also nicht. **Strukturierte Ausgabe** über `output_config.format` ist der vorgesehene Weg und lässt sich mit Werkzeugen kombinieren.
- Kosten laut Preisliste [Q25] (USD pro Million Tokens, Eingabe/Ausgabe): Opus 5.5 4/20, Sonnet 5.5 2/10, Haiku 5.5 0,10/0,50 (bis 100k Token Prompt). Cache-Treffer bei Opus 5.5 kosten das 0,05-Fache des Eingabepreises [Q25]. Weil System-Prompt und Werkzeugliste bei jeder Diagnose gleich sind, lohnt sich **Prompt-Caching**, vor allem bei den vielen Läufen der Auswertung.

**Warum eine eigene Schleife und nicht …**

| Option | Was es ist | Warum (nicht) für RootPing |
|---|---|---|
| **Eigene Schleife (Messages API)** ✔ | ~40 Zeilen: Anfrage, Werkzeug ausführen, Ergebnis zurück, bis fertig | Volle Kontrolle über genau die Dinge, die die Auswertung braucht: Höchstzahl Werkzeugaufrufe, Traceroute-Limit, Kosten und Tokens pro Schritt protokollieren, Abbruchgründe (`max_tokens`, `refusal`) sauber behandeln. **Im Gespräch voll erklärbar.** Keine Beta-Abhängigkeit. |
| Tool Runner (`client.beta.messages.tool_runner`) | SDK-Helfer, der die Schleife übernimmt | Gute Alternative, spart ~20 Zeilen. Ist aber **Beta** im Python-SDK, und die Schleife ist hier gerade der Teil, den man zeigen und kontrollieren will. |
| Claude Agent SDK (`claude-agent-sdk` 0.2.189) | Claude Code als Bibliothek, mit eingebauten Werkzeugen (Dateien lesen/schreiben, Bash, Websuche) [Q27] | Falsches Werkzeug: RootPing braucht genau **keine** Datei- und Shell-Werkzeuge auf dem Rechner des Nutzers. Das Windows-Wheel ist **178 MB** groß [Q8], weil es Claude Code mitbringt. Version 0.x. |
| Claude Managed Agents | Anthropic betreibt Schleife und eine Sandbox in der Cloud; eigene Werkzeuge werden an den eigenen Rechner zurückgegeben | Die Werkzeuge müssen ohnehin **lokal** laufen (Router anpingen, lokale DB lesen). Managed Agents ist **Beta**, berechnet zusätzlich Laufzeit ($0,08 pro Session-Stunde [Q25]) und speichert den Verlauf bei Anthropic, bis man ihn löscht. Für einen kurzen, lokalen Diagnose-Lauf ist das mehr Infrastruktur als Nutzen. Es wäre eine legitime Alternative, wenn RootPing später als gehosteter Dienst laufen soll. |
| Frameworks (LangChain, PydanticAI, …) | Abstraktion über mehrere Anbieter | Zusätzliche Schicht ohne Nutzen, da nur Claude verwendet wird; verdeckt genau das, was das Projekt zeigen soll. |

**Modellwahl ❓:** Die Modellübersicht von Anthropic empfiehlt **Claude Opus 5.5** (`claude-opus-5-5`) als Einstiegsmodell, wenn man unsicher ist [Q45, abgerufen 26.11.2026]. Für die Auswertung bietet sich an, **dasselbe Szenario-Set zusätzlich mit Sonnet 5.5 und Haiku 5.5** laufen zu lassen. Das beantwortet die im Gespräch naheliegende Frage „Braucht man dafür das große Modell?“ mit Zahlen. Das ist Kais Entscheidung (Abschnitt 5).

**Weitere Einstellungen (aus der Anthropic-Doku):** Auf Opus 5.5 lässt sich das Nachdenken nicht abschalten; gesteuert wird über `output_config.effort` (Standard dort `medium`; Nachdenken adaptiv und immer an [Q45]), der Wert kommt aus der Konfiguration. Ein serverseitiger Fallback bei Ablehnungen (`fallbacks`) existiert als Beta; bei Netzwerkdiagnosen sind Ablehnungen unwahrscheinlich, der Parameter kann trotzdem konfigurierbar vorgesehen werden. `stop_reason` wird vor dem Lesen des Inhalts immer geprüft.

**Unsicher:** Konkrete Kosten pro Diagnose hängen von Prompt-Länge und Anzahl der Werkzeugaufrufe ab und sind erst nach den ersten Läufen messbar. Deshalb werden Tokens und Kosten pro Diagnose von Anfang an gespeichert (Datenmodell hat die Spalten).

### 3.21 Verteilung unter Windows ➕

**Empfehlung für v1:** **`uv tool install git+https://github.com/trais92/rootping`** (bzw. `uvx` zum einmaligen Ausprobieren). Das installiert RootPing samt passender Python-Version isoliert; der Befehl `rootping` steht danach im Pfad. Keine `.exe` in v1 (passt zu „Releases für alle Systeme“ = nicht in v1).

**Begründung:** Für technische Nutzer (und Personaler, die es mit Anleitung testen) ist das laut einer Übersicht von 09/2026 der Standardweg [Q42]. Kein Code-Signing, keine Virenscanner-Fehlalarme.

**Später, falls eine `.exe` gewünscht ist:** PyApp (kleiner Starter, lädt Python beim ersten Start) oder PyInstaller/Nuitka (alles in einer Datei). Bei allen dreien sind **Fehlalarme von Virenscannern häufig** und Code-Signing ist nicht automatisch [Q42]. Hinweis: Das Repo ist derzeit privat; für `uv tool install` von außen muss es öffentlich sein oder auf PyPI liegen.

### 3.22 Sicherheit und Lieferkette ➕

| Maßnahme | Umsetzung | Quelle |
|---|---|---|
| Feste Versionen | `uv.lock` im Repo, CI mit `uv sync --locked` | [Q29], T9 |
| Cooldown für neue Releases | `exclude-newer = "7 days"` | [Q29], T9 |
| Automatische Updates mit Cooldown | Dependabot für `uv` und `github-actions`, `cooldown: default-days: 7` (passend zum uv-Cooldown, sonst schlägt Dependabot unlösbare Versionen vor) | [Q30] |
| Actions gepinnt | Auf volle Commit-SHA **und** GitHub-Workflow-Lockfile (`.github/workflows/actions.lock`, GA seit 28.10.2026, auch im Free-Plan) | [Q40] |
| Warum SHA allein nicht reicht | 2026 wurden Angriffe bekannt, bei denen eine gepinnte SHA auf einen Commit aus einem **Fork** zeigte (Fall Trivy, März 2026); SHA garantiert Unveränderlichkeit, nicht Herkunft. Workflow-Lockfiles verlangen, dass der Commit im Quell-Repo existiert. | [Q41] (Sekundärquelle, The Hacker News, 24.11.2026) |
| Workflow-Prüfung | `zizmor` (statische Analyse für GitHub Actions) in CI | [Q8] |
| Minimale Rechte | `permissions: contents: read` als Standard | GitHub-Empfehlung |
| Geheimnisse | API-Schlüssel nur über Umgebungsvariable bzw. GitHub Secrets; nie in `config.toml`; Push-Schutz für Secrets aktivieren | – |
| Datenschutz | Nur zusammengefasste Werte an die API; private IPs durch Platzhalter (wie im Plan) | [projektplan.md](projektplan.md) |
| Eingeschleuste Texte (Prompt Injection) | Werkzeugergebnisse an die KI enthalten nur Zahlen, IPs und feste Fehlercodes; Traceroute ohne Namensauflösung (`-d`/`-n`), DNS-Antworten werden nicht inhaltlich weitergegeben | eigene Überlegung |
| Unterprozesse | Nur Traceroute, immer `create_subprocess_exec` mit Argumentliste, nie `shell=True`; Ziel vorher als IP/Hostname validiert | ruff `S603` |

**Verworfen:** *`pip-audit` als Pflichtschritt:* gut, aber Dependabot-Sicherheitswarnungen decken das im GitHub-Workflow ab; `uv audit` ist experimentell (3.2).

**Unsicher:** Ob Workflow-Lockfiles für **private** Repos im Free-Plan gelten, sagt die Ankündigung nicht ausdrücklich [Q40]. Spätestens wenn das Repo öffentlich wird, ist es verfügbar.

---

## 4. Auswirkungen auf die bestehende Doku

Diese Änderungen schlage ich vor. **Nichts davon ist schon umgesetzt**, außer der Statuszeile von ADR-004, den neuen ADRs 006–010 (Status „vorgeschlagen“) und einem Verweis in [projektplan.md](projektplan.md) auf dieses Dokument. Die Anpassungen an `probes.md`, `diagnose.md` und `projektplan.md` mache ich, sobald Kai die offenen Punkte entschieden hat.

| Datei | Änderung | Grund |
|---|---|---|
| [adr/004](adr/004-ping-ohne-adminrechte.md) | Statuszeile: „Ersatz vorgeschlagen durch ADR-006“ (schon geändert); nach Kais Zustimmung „ersetzt durch ADR-006“. Inhalt bleibt, wie es die ADR-Regeln verlangen. | B1 |
| [probes.md](probes.md) | Ping-Konfiguration: `count`/`packet_interval` durch „1 Echo pro Sekunde, Runde = 10 s“ ersetzen; Timeout ≤ Paketabstand empfohlen oder überlappend erlaubt; `settings: dict` → Pydantic-Modell; Windows-Hinweis neu | B1, B2, 3.13 |
| [diagnose.md](diagnose.md) | Jitter-Definition festschreiben; Hinweis zu DNS-Ziel „gateway“ und Cache-Effekt | 3.8, 3.10 |
| [projektplan.md](projektplan.md) | Technik-Tabelle (Abschnitt 6) auf diese Datei verweisen; Python 3.14+; Risiko „Ping ohne Admin“ auf „gelöst durch ICMP-API, Spike bestätigt“ setzen | 3.1, 3.8 |
| Installationsanleitung (README) | Linux: Hinweis auf `ping_group_range`; Windows: keine Adminrechte nötig | B3 |

---

## 5. Offene Entscheidungen für Kai

| # | Frage | Optionen | Empfehlung |
|---|---|---|---|
| E1 | **Python-Version** | A) Untergrenze 3.14, entwickelt auf 3.15, CI beide · B) nur 3.15 · C) nur 3.14 | **A**: aktuell, aber mit getesteter Rückfallebene |
| E2 | **Ping unter Windows** | A) Windows-ICMP-API über `ctypes` (eigener Code, ~80 Zeilen) · B) System-`ping` aufrufen · C) Bibliothek `ipscout` | **A**: ohne Admin, ohne Unterprozess, gut erklärbar, keine junge Abhängigkeit |
| E3 | **Ping-Takt** | A) fester 1-s-Takt, Statistik selbst berechnet · B) bei `icmplib`-Verhalten bleiben und Konfiguration anpassen | **A**: B2 zeigt, dass B gerade bei Störungen falsche Zeitfenster liefert |
| E4 | **Typprüfer** | A) Pyright jetzt, ty später prüfen · B) ty sofort (Beta) · C) mypy | **A** |
| E5 | **Agent-Ansatz** | A) eigene Schleife auf der Messages API · B) Tool Runner (Beta) · C) Managed Agents | **A** |
| E6 | **Modelle in der Auswertung** | A) nur Opus 5.5 · B) Opus 5.5 + Sonnet 5.5 + Haiku 5.5 im Vergleich | **B**, wenn das Budget passt: macht die Auswertung aussagekräftiger |
| E7 | **DNS „system“ unter Linux** | A) zusätzliches Ziel „gateway“ · B) so lassen und Grenze dokumentieren | **A** |

**Ein Test, den Kai sofort selbst machen kann (2 Minuten, Windows, normales Terminal ohne „Als Administrator ausführen“):**

```powershell
uv run --no-project --with icmplib python -c "from icmplib import ping; print(ping('1.1.1.1', count=2, privileged=False))"
```

Erwartung laut Quellcode und Microsoft-Doku: **`SocketPermissionError`**. Kommt stattdessen ein Ergebnis, ist B1 widerlegt, und ich passe die Empfehlung an. (Der Befehl installiert nichts dauerhaft, uv legt eine temporäre Umgebung an. Er setzt voraus, dass uv installiert ist. Unter Linux mit `127.0.0.1` getestet, Ausgabe in [belege.md](recherche/belege.md#t2).)

---

## 6. Was ich nicht prüfen konnte

- Windows-Verhalten von `IcmpSendEcho2` und `GetBestRoute` aus Python (kein Windows-Rechner; Spike in Sprint 1).
- Ob `QueryPerformanceCounter` (Basis von `time.monotonic()` unter Windows seit 3.13) den Ruhezustand mitzählt; das Design hängt bewusst nicht davon ab (3.7).
- SQLite-Commit-Zeiten unter Windows mit Virenscanner (3.12).
- Echte Latenzen ins Internet (in der Testumgebung gesperrt).
- Kosten pro Diagnose (erst nach ersten API-Läufen messbar).
- Aktuelle Konformitätszahlen der Typprüfer nach Mai 2026.

---

## 7. Quellen

Alle abgerufen am **26.11.2026**, sofern nicht anders angegeben.

| Nr. | Quelle |
|---|---|
| Q1 | Python Developer's Guide, Status of Python versions: https://devguide.python.org/versions/ |
| Q2 | Python 3.15.0 Release-Seite: https://python.org/downloads/release/python-3150/ |
| Q3 | PEP 686, Make UTF-8 mode default: https://peps.python.org/pep-0686/ |
| Q4 | What's New in Python 3.13 (time.monotonic unter Windows): https://docs.python.org/3/whatsnew/3.13.html |
| Q5 | What's New in Python 3.14: https://docs.python.org/whatsnew/3.14.html |
| Q6 | PEP 418, monotonic time (Tabelle „Include Suspend“): https://peps.python.org/pep-0418/ |
| Q7 | asyncio Platform Support (Windows): https://docs.python.org/pl/3.15/library/asyncio-platforms.html |
| Q8 | PyPI JSON API, `https://pypi.org/pypi/<paket>/json`, abgefragt 26.11.2026 (Versionen, Daten, Abhängigkeiten, Wheels; siehe Anhang A). Quellcode von icmplib 3.0.4 und dnspython 2.9.2 aus den PyPI-Paketen. |
| Q9 | icmplib 3.0.4 Quellcode und README (sdist von PyPI): `icmplib/sockets.py` Z. 81–97, `icmplib/ping.py` (`async_ping`), `icmplib/models.py` (`jitter`); Projekt: https://github.com/ValentinBELYN/icmplib |
| Q10 | Microsoft Learn, TCP/IP Raw Sockets: https://learn.microsoft.com/en-us/windows/win32/winsock/tcp-ip-raw-sockets-2 |
| Q11 | Microsoft Learn, IcmpSendEcho2Ex: https://learn.microsoft.com/en-us/windows/win32/api/icmpapi/nf-icmpapi-icmpsendecho2ex |
| Q12 | Microsoft Learn, ICMP_ECHO_REPLY: https://learn.microsoft.com/en-us/windows/win32/api/Ipexport/ns-ipexport-icmp_echo_reply |
| Q13 | Stack Overflow (Archiv), „How come ping doesn't need administrative privileges on Windows?“ (Sekundärquelle): https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/11439011/how-come-ping-doesn-t-need-administrative-privileges-on-windows |
| Q14 | Linux-Kernel-Doku zu `ping_group_range` (Patch auf lore.kernel.org): https://lore.kernel.org/all/20200422.192940.1685473383760448858.davem@davemloft.net/T/ |
| Q15 | systemd, `sysctl.d/50-default.conf`: https://third-party-mirror.googlesource.com/systemd/+/refs/heads/master/sysctl.d/50-default.conf |
| Q16 | Fedora Change „EnableSysctlPingGroupRange“: https://www.fedoraproject.org/wiki/Changes/EnableSysctlPingGroupRange |
| Q17 | Microsoft Learn, GetBestRoute: https://learn.microsoft.com/en-us/windows/win32/api/iphlpapi/nf-iphlpapi-getbestroute |
| Q18 | ipscout auf PyPI: https://pypi.org/project/ipscout/ |
| Q19 | winping: https://github.com/Snawoot/winping |
| Q20 | MCP Python SDK, Migration Guide v1 → v2: https://py.sdk.modelcontextprotocol.io/migration/ |
| Q21 | MCP Python SDK Releases: https://github.com/modelcontextprotocol/python-sdk/releases |
| Q22 | MCP-Spezifikation 2026-07-28, stdio-Transport: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio |
| Q23 | Anthropic Python SDK, MIGRATION.md: https://github.com/anthropics/anthropic-sdk-python/blob/main/MIGRATION.md |
| Q24 | Claude API, Migration auf API-Version 2026-10-21: https://platform.claude.com/docs/en/api/migration-2026-10-21 |
| Q25 | Claude API, Pricing: https://platform.claude.com/docs/en/about-claude/pricing |
| Q26 | Claude API, Tool use overview: https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview |
| Q27 | Claude Agent SDK overview: https://code.claude.com/docs/en/agent-sdk.md |
| Q29 | pydevtools, „How to protect against Python supply chain attacks with uv“ (verifiziert mit uv 0.13): https://pydevtools.com/handbook/how-to/how-to-protect-against-python-supply-chain-attacks-with-uv/ |
| Q30 | uv-Doku, Dependabot: https://docs.astral.sh/uv/guides/integration/dependabot/ |
| Q31 | „mypy vs Pyright vs ty“ (Blog, 16.04.2026, aktualisiert Mai 2026; Sekundärquelle): https://www.danilchenko.dev/posts/ty-vs-mypy-vs-pyright/ |
| Q32 | pydevtools Handbook, ty: https://pydevtools.com/handbook/topics/ty/ |
| Q33 | prek: https://prek.j178.dev/ |
| Q34 | Material for MkDocs Blog, „MkDocs 2.0“ (mit Nachträgen bis 09/2026): https://squidfunk.github.io/mkdocs-material/blog/2026/02/18/mkdocs-2.0 |
| Q35 | Typer Release Notes: https://typer.tiangolo.com/release-notes/ |
| Q36 | pytest-asyncio Changelog: https://pytest-asyncio.readthedocs.io/en/stable/reference/changelog.html |
| Q37 | GitHub Docs, GitHub-hosted runners: https://docs.github.com/en/actions/reference/runners/github-hosted-runners |
| Q38 | GitHub Changelog 17.09.2026, Ubuntu 26 / latest-Migration: https://github.blog/changelog/2026-09-17-ubuntu-26-generally-available-and-latest-migration |
| Q39 | GitHub Changelog 14.05.2026, Image-Migrationen: https://github.blog/changelog/2026-05-14-github-actions-upcoming-image-migrations |
| Q40 | GitHub Changelog 28.10.2026, Workflow-Lockfiles GA: https://github.blog/changelog/2026-10-28-github-actions-workflow-lockfiles-are-generally-available/ |
| Q41 | The Hacker News, 24.11.2026 (Sekundärquelle): https://thehackernews.com/2026/11/hackers-found-way-around-github-sha.html |
| Q42 | pydevtools, „How do I ship a Python application to end users?“ (Stand 07.09.2026): https://pydevtools.com/handbook/explanation/how-do-i-ship-a-python-application-to-end-users/ |
| Q43 | Python Bug Tracker, Issue 4749 (RotatingFileHandler unter Windows): https://bugs.python.org/issue4749 |
| Q44 | systemd-resolved.service(8): https://man7.org/linux/man-pages/man8/systemd-resolved.service.8.html |
| Q45 | Anthropic, Models overview (abgerufen 26.11.2026): https://platform.claude.com/docs/en/about-claude/models/overview |

(Q28 entfällt; die Wheel-Größe des Agent SDK stammt aus Q8.)

---

## Anhang A: Versionen (Stand 26.11.2026)

Abgefragt über die PyPI-JSON-API [Q8]. „Mind. Python“ = `requires_python` des Pakets.

| Paket | Version | Datum | Mind. Python | Rolle |
|---|---|---|---|---|
| uv | 0.13.10 | 24.11.2026 | – | Paketverwaltung |
| ruff | 0.17.6 | 19.11.2026 | – | Lint/Format |
| pyright | 1.1.414 | 10.09.2026 | – | Typprüfung |
| ty | 0.0.111 | 25.11.2026 | – | (beobachten) |
| mypy | 2.4.1 | 28.10.2026 | 3.10 | (verworfen) |
| prek | 0.5.12 | 26.11.2026 | – | Git-Hooks |
| pytest | 9.2.0 | 27.10.2026 | 3.10 | Tests |
| pytest-asyncio | 1.5.0 | 12.11.2026 | 3.10 | Tests |
| hypothesis | 6.170.17 | 20.11.2026 | 3.11 | Tests |
| icmplib | 3.0.4 | **10.10.2023** | 3.7 | Ping (Linux) |
| dnspython | 2.9.2 | 03.11.2026 | 3.11 | DNS |
| pydantic | 2.14.4 | 19.11.2026 | 3.10 | Validierung |
| pydantic-settings | 2.16.3 | 13.11.2026 | 3.11 | Konfiguration |
| typer | 0.29.3 | 26.11.2026 | 3.11 | CLI |
| platformdirs | 4.14.8 | 20.11.2026 | 3.11 | Pfade |
| anthropic | 2.14.0 | 24.11.2026 | 3.10 | Claude API |
| mcp | 2.3.0 | 02.10.2026 | 3.10 | MCP-Server |
| claude-agent-sdk | 0.2.189 | 25.11.2026 | 3.10 | (verworfen) |
| apscheduler | 3.11.3 (4.0.0a6) | 28.06.2026 | 3.8 | (verworfen) |
| ipscout | 2.5.4 | (erstes Release 29.07.2026) | 3.10 | (verworfen) |
| zizmor | 1.33.1 | 22.11.2026 | 3.11 | CI-Prüfung |

Python-Versionen, die uv 0.13.10 am 26.11.2026 anbot: 3.15.2, 3.14.10 (T1).
