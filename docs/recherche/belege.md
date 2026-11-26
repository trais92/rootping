# Belege zur Tech-Stack-Recherche (Tests T1–T10)

> Gehört zu [../tech-stack.md](../tech-stack.md) · durchgeführt am **26.11.2026**

Diese Datei enthält die Tests, auf die sich [tech-stack.md](../tech-stack.md) beruft: was genau ausgeführt wurde und was herauskam. Ziel ist, dass jede Aussage nachprüfbar ist. Die Skripte sind **Wegwerf-Code zur Überprüfung**, kein Teil von RootPing; deshalb stehen sie hier als Textblöcke und nicht als Dateien im Projekt.

**Umgebung (für alle Tests gleich)**

| | |
|---|---|
| System | Linux-Container (x86_64), Benutzer root, **ohne systemd** |
| Python | 3.15.2 (über uv installiert) |
| uv | 0.13.10 |
| Pakete | anthropic 2.14.0, mcp 2.3.0, icmplib 3.0.4, dnspython 2.9.2, pydantic-settings 2.16.3, typer 0.29.3, platformdirs 4.14.8, pytest 9.2.0, pytest-asyncio 1.5.0, hypothesis 6.170.17, ruff 0.17.6, ty 0.0.111, pyright 1.1.414 |
| Netz | Ausgehendes ICMP gesperrt: jedes Echo an eine externe Adresse geht verloren. Lokal (`127.0.0.1`) funktioniert. |
| Nicht verfügbar | Windows, Claude-API-Schlüssel (bewusst keine kostenpflichtigen Aufrufe) |

---

## T1: Projekt anlegen, alle Kandidaten unter Python 3.15 installieren

```bash
uv python list                       # zeigt u. a. cpython-3.15.2, cpython-3.14.10
uv init --package --python 3.15 rpspike
cd rpspike
uv add icmplib dnspython "mcp>=2.3" "anthropic>=2.14" pydantic-settings typer platformdirs
uv add --dev pytest pytest-asyncio hypothesis ruff ty pyright
uv run python -c "import sys,sqlite3;print(sys.version);print(sqlite3.sqlite_version)"
```

Ergebnis:

```
3.15.2 (main, Nov 24 2026, 17:00:04) [Clang 23.1.3 ]
3.54.1
```

Die von `uv init --package` erzeugte `pyproject.toml` nutzt das src-Layout und `build-backend = "uv_build"` (`requires = ["uv_build>=0.13.10,<0.14.0"]`). Alle Pakete ließen sich ohne Fehler installieren.

---

## T2: Unprivilegierter Ping unter Linux hängt von `ping_group_range` ab {#t2}

```python
import asyncio
from icmplib import async_ping

async def main():
    for host in ["127.0.0.1", "1.1.1.1"]:
        for priv in (False, True):
            try:
                r = await async_ping(host, count=3, interval=0.2, timeout=1, privileged=priv)
                print(host, "priv=", priv, "recv", r.packets_received, "avg", r.avg_rtt, "loss", r.packet_loss)
            except Exception as e:
                print(host, "priv=", priv, type(e).__name__, e)

asyncio.run(main())
```

**Lauf 1**, Ausgangszustand `cat /proc/sys/net/ipv4/ping_group_range` → `1 0` (Kernel-Standard):

```
127.0.0.1 priv= False SocketPermissionError A prior configuration of your OS is required to use ICMP sockets without root privileges. ...
127.0.0.1 priv= True recv 3 avg 0.127 loss 0.0        # Raw Socket klappt nur, weil der Test als root läuft
1.1.1.1   priv= False SocketPermissionError ...
1.1.1.1   priv= True recv 0 avg 0.0 loss 1.0          # extern gesperrt
```

**Lauf 2**, nach `echo "0 2147483647" > /proc/sys/net/ipv4/ping_group_range` (Wert, den systemd setzt):

```
127.0.0.1 priv= False recv 3 avg 0.095 loss 0.0      # unprivilegierter Datagram-Socket funktioniert
127.0.0.1 priv= True  recv 3 avg 0.09  loss 0.0
1.1.1.1   priv= False recv 0 avg 0.0 loss 1.0
1.1.1.1   priv= True  recv 0 avg 0.0 loss 1.0
```

**Schluss:** Der unprivilegierte Weg funktioniert unter Linux, aber nur, wenn `ping_group_range` die Gruppe erlaubt (Befund B3).

Zusätzlich der Test-Einzeiler aus Abschnitt 5 von tech-stack.md (mit lokalem Ziel):

```bash
uv run --no-project --with icmplib python -c "from icmplib import ping; print(ping('127.0.0.1', count=2, privileged=False))"
# Packets sent: 2 / Packets received: 2 / Packet loss: 0.0% / Round-trip times: 0.073 ms / 0.103 ms / 0.132 ms
```

---

## T3: `icmplib.async_ping(count=N)` vs. fester 1-Sekunden-Takt

```python
"""Vergleich: icmplib async_ping(count=N) vs. fester 1-s-Takt mit Einzel-Echos."""
import asyncio, time
from icmplib import async_ping

async def echo_once(host: str, timeout: float) -> float | None:
    h = await async_ping(host, count=1, timeout=timeout, privileged=False)
    return h.avg_rtt if h.packets_received else None

async def fixed_rate_round(host: str, count: int, period: float, timeout: float) -> list[float | None]:
    loop = asyncio.get_running_loop()
    start = loop.time()
    async with asyncio.TaskGroup() as tg:
        tasks = []
        for i in range(count):
            # auf den festen Takt warten (driftfrei), dann Echo starten, ohne auf die Antwort zu warten
            await asyncio.sleep(max(0.0, start + i * period - loop.time()))
            tasks.append(tg.create_task(echo_once(host, timeout)))
    return [t.result() for t in tasks]

async def main():
    host, n = "1.1.1.1", 5   # in dieser Umgebung geht jedes externe Echo verloren
    t = time.perf_counter(); h = await async_ping(host, count=n, interval=1, timeout=2, privileged=False)
    print(f"icmplib count={n}: {time.perf_counter()-t:.1f}s, received={h.packets_received}")
    t = time.perf_counter(); r = await fixed_rate_round(host, n, 1.0, 2.0)
    print(f"fester Takt   n={n}: {time.perf_counter()-t:.1f}s, results={r}")
    t = time.perf_counter(); r = await fixed_rate_round("127.0.0.1", n, 1.0, 2.0)
    print(f"fester Takt lokal: {time.perf_counter()-t:.1f}s, results={[round(x, 3) for x in r]}")

asyncio.run(main())
```

Ergebnis:

```
icmplib count=5: 14.0s, received=0
fester Takt   n=5: 6.0s, results=[None, None, None, None, None]
fester Takt lokal: 4.0s, results=[0.093, 0.072, 0.092, 0.083, 0.07]
```

**Erklärung:** `async_ping` wartet nach jedem Paket auf Antwort oder Timeout (2 s) und schläft dann `interval` (1 s): 5 × 2 s + 4 × 1 s = 14 s. Der feste Takt sendet zu 0, 1, 2, 3, 4 s; das letzte Echo hat 2 s Timeout: 6 s. Bei 10 Paketen wären es 29 s gegenüber 11 s. Das bestätigt den Quellcode von `icmplib/ping.py` (Befund B2). Der feste Takt funktioniert mit mehreren gleichzeitig offenen Ping-Sockets.

---

## T4: MCP Python SDK 2.3 (Server und Client)

Server:

```python
"""Mini MCP-Server zum Testen von mcp 2.x."""
from pydantic import BaseModel
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("rootping-spike")

class PingSummary(BaseModel):
    target: str
    avg_ms: float
    loss_pct: float

@mcp.tool()
async def get_recent_measurements(probe: str, minutes: int = 5) -> list[PingSummary]:
    """Liefert die letzten Messrunden einer Probe."""
    return [PingSummary(target="1.1.1.1", avg_ms=12.3, loss_pct=0.0)]

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Client:

```python
import asyncio, sys
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

async def main():
    async with stdio_client(StdioServerParameters(command=sys.executable, args=["mcp_srv.py"])) as (r, w):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            print("protocol", init.protocol_version)
            tools = await s.list_tools()
            for t in tools.tools:
                print(t.name, "|", t.description, "| out:", bool(t.output_schema))
            res = await s.call_tool("get_recent_measurements", {"probe": "ping_internet"})
            print("structured:", res.structured_content)

asyncio.run(main())
```

Ergebnis:

```
protocol 2025-11-25
get_recent_measurements | Liefert die letzten Messrunden einer Probe. | out: True
structured: {'result': [{'target': '1.1.1.1', 'avg_ms': 12.3, 'loss_pct': 0.0}]}
```

**Beobachtungen**
- `MCPServer` aus `mcp.server.mcpserver` funktioniert; der Docstring wird zur Werkzeugbeschreibung, der Pydantic-Rückgabetyp zum Ausgabe-Schema.
- Der erste Client-Versuch mit den 1.x-Attributnamen schlug fehl: `AttributeError: 'Tool' object has no attribute 'outputSchema'. Did you mean '.output_schema'?`. In 2.x heißen sie `output_schema`, `structured_content`, `protocol_version`.
- Ausgehandelte Protokollversion: `2025-11-25` (Handshake-Version), siehe tech-stack.md 3.19.

---

## T5: SQLite (STRICT, WAL, JSON, user_version, datetime-Adapter)

Lauf mit `python -W error::DeprecationWarning` (Warnungen werden zu Fehlern, damit sie sichtbar sind).

**Erster Versuch** (Verbindung mit `autocommit=False`, danach `PRAGMA journal_mode=WAL`):

```
sqlite3.OperationalError: cannot change into wal mode from within a transaction
```

**Zweiter Versuch** (PRAGMAs zuerst im Autocommit-Modus, dann `con.autocommit = False`):

```python
import sqlite3, datetime, tempfile, os
p = os.path.join(tempfile.mkdtemp(), "t.db")
con = sqlite3.connect(p, autocommit=True)
print("journal", con.execute("PRAGMA journal_mode=WAL").fetchone(), "sqlite", sqlite3.sqlite_version)
con.execute("PRAGMA foreign_keys=ON"); con.execute("PRAGMA busy_timeout=5000")
con.autocommit = False
con.execute("""CREATE TABLE measurements(id INTEGER PRIMARY KEY, ts TEXT NOT NULL, probe TEXT NOT NULL,
 ok INTEGER NOT NULL CHECK (ok IN (0,1)), latency_ms REAL,
 details TEXT CHECK (details IS NULL OR json_valid(details))) STRICT""")
con.execute("INSERT INTO measurements(ts,probe,ok,latency_ms,details) VALUES (?,?,?,?,?)",
            ("2026-11-26T12:00:00.000Z", "ping", 1, 12.5, '{"a":1}'))
try:
    con.execute("INSERT INTO measurements(ts,probe,ok,latency_ms) VALUES (?,?,?,?)", ("x", "ping", 1, "abc"))
except sqlite3.Error as e:
    print("STRICT rejects:", type(e).__name__, e)
print(con.execute("SELECT json_extract(details,'$.a') FROM measurements").fetchone())
con.execute("PRAGMA user_version=1"); con.commit()
print("user_version", con.execute("PRAGMA user_version").fetchone())
try:
    con.execute("INSERT INTO measurements(ts,probe,ok) VALUES (?,?,?)", (datetime.datetime.now(datetime.UTC), "p", 1))
except Exception as e:
    print("datetime adapter:", type(e).__name__, e)
```

Ergebnis:

```
journal ('wal',) sqlite 3.54.1
STRICT rejects: IntegrityError cannot store TEXT value in REAL column measurements.latency_ms
(1,)
user_version (1,)
datetime adapter: DeprecationWarning The default datetime adapter is deprecated as of Python 3.12; see the sqlite3 documentation for suggested replacement recipes
```

---

## T6: Gleichzeitiges Lesen (nur lesend) und Commit-Dauer

**Leser mit `mode=ro` neben einem Schreiber mit offener Transaktion:**

```python
import sqlite3, tempfile, os, pathlib
p = os.path.join(tempfile.mkdtemp(), "r.db")
w = sqlite3.connect(p, autocommit=True); w.execute("PRAGMA journal_mode=WAL"); w.execute("CREATE TABLE t(x INTEGER) STRICT")
w.autocommit = False; w.execute("INSERT INTO t VALUES (1)")            # offene Schreibtransaktion
r = sqlite3.connect(pathlib.Path(p).as_uri() + "?mode=ro", uri=True)
print("reader sees (uncommitted hidden):", r.execute("SELECT count(*) FROM t").fetchone())
w.commit(); print("after commit:", r.execute("SELECT count(*) FROM t").fetchone())
try: r.execute("INSERT INTO t VALUES (2)")
except sqlite3.OperationalError as e: print("ro blocks writes:", e)
```

```
reader sees (uncommitted hidden): (0,)
after commit: (1,)
ro blocks writes: attempt to write a readonly database
```

**Commit-Dauer** (6 Zeilen pro Transaktion, 200 Wiederholungen, WAL):

```
NORMAL median ms 0.01 p99 0.029
FULL   median ms 0.282 p99 0.528
```

Achtung: gemessen im Linux-Container. Unter Windows mit NTFS und Virenscanner nicht gemessen.

---

## T7: Anthropic SDK 2.14 (nur Signaturen, keine API-Aufrufe)

```python
import anthropic, inspect
print(anthropic.__version__)
from anthropic import beta_async_tool, beta_tool
c = anthropic.AsyncAnthropic(api_key="x")
print("parse" in dir(c.messages), "tool_runner" in dir(c.beta.messages))
sig = inspect.signature(c.messages.create)
print([p for p in sig.parameters if p in ("output_config","thinking","temperature","fallbacks","tool_choice","cache_control","speed")])
import anthropic.lib.tools.mcp as m; print([n for n in dir(m) if "mcp" in n])
```

```
2.14.0
True True
['cache_control', 'output_config', 'speed', 'thinking', 'tool_choice']
['_mcp_field_v1_or_v2', 'async_mcp_tool', 'mcp_content', 'mcp_message', 'mcp_resource_to_content', 'mcp_resource_to_file', 'mcp_tool']
```

**Schluss:** `temperature` ist nicht mehr Teil von `messages.create` (passt zur API-Version 2026-10-21). `output_config` (strukturierte Ausgabe, Effort) ist vorhanden. `fallbacks` ist nicht im normalen Endpunkt (Beta-Endpunkt). Der Tool Runner liegt unter `beta`.

---

## T8: Konfiguration mit pydantic-settings (TOML + Umgebungsvariablen)

`cfg.toml`:

```toml
[probes.ping_internet]
enabled = true
targets = ["1.1.1.1", "9.9.9.9"]
interval = 10
[thresholds]
latency_ms_internet = 60
```

```python
import os
from pydantic import BaseModel, PositiveFloat
from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource

class PingSettings(BaseModel):
    enabled: bool = True
    targets: list[str]
    interval: PositiveFloat = 10

class Thresholds(BaseModel):
    latency_ms_internet: float = 60

class Settings(BaseSettings):
    model_config = SettingsConfigDict(toml_file="cfg.toml", env_prefix="ROOTPING_",
                                      env_nested_delimiter="__", extra="forbid")
    probes: dict[str, PingSettings]
    thresholds: Thresholds = Thresholds()

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        return (init_settings, env_settings, TomlConfigSettingsSource(settings_cls))

os.environ["ROOTPING_THRESHOLDS__LATENCY_MS_INTERNET"] = "45"
print(Settings().model_dump())
os.environ["ROOTPING_THRESHOLDS__LATENCY_MS_INTERNET"] = "abc"
try: Settings()
except Exception as e: print(type(e).__name__, str(e).splitlines()[0:3])
```

```
{'probes': {'ping_internet': {'enabled': True, 'targets': ['1.1.1.1', '9.9.9.9'], 'interval': 10.0}}, 'thresholds': {'latency_ms_internet': 45.0}}
ValidationError ['1 validation error for Settings', 'thresholds.latency_ms_internet', "  Input should be a valid number, unable to parse string as a number [type=float_parsing, input_value='abc', input_type=str]"]
```

---

## T9: uv-Cooldown, Lockfile, `uv audit`

```bash
printf '\n[tool.uv]\nexclude-newer = "7 days"\n' >> pyproject.toml
uv lock
```

```
Resolving despite existing lockfile: Global exclude-newer cutoff set: 2026-11-19T13:52:48Z
error: No solution found when resolving dependencies
  cause: Because anthropic>2.10.0 was published after the exclude newer time and your project depends on anthropic>=2.14, ...
```

Nach Absenken auf `anthropic>=2.0` scheiterte es an `platformdirs>=4.14.8` (von `uv add` gesetzt, 6 Tage alt). Nach Absenken aller von `uv add` gesetzten Untergrenzen:

```
rpspike v0.1.0
├── anthropic v2.10.0
├── dnspython v2.9.2
├── icmplib v3.0.4
├── mcp v2.3.0
├── platformdirs v4.14.7
├── pydantic-settings v2.16.3
├── typer v0.29.2
...
```

`grep -c "hash = " uv.lock` → `328` (59 Pakete).

```bash
uv audit
# warning: `uv audit` is experimental and may change without warning. ...
# (Abfrage an api.osv.dev in dieser Umgebung blockiert)
```

**Schluss:** Der Cooldown wirkt wie beschrieben. Untergrenzen müssen zum Cooldown passen; `uv audit` ist experimentell.

---

## T10: ruff-Docstring-Regeln, ty und Pyright, Regelnamen, Python 3.15

Absichtlich fehlerhafte Datei:

```python
def summarize(rtts: list[float | None]) -> float:
    return max(r for r in rtts if r is not None) + "1"
```

```bash
uv run ruff check --select D,ANN --config 'lint.pydocstyle.convention="google"' x.py
uv run ty check x.py
uv run pyright x.py
```

```
D100 Missing docstring in public module
D103 Missing docstring in public function
error[unsupported-operator]: Unsupported `+` operation                       (ty)
error: Operator "+" not supported for types "float" and "Literal['1']"        (pyright)
```

Regelnamen geprüft mit `ruff rule <code>`: `PLW1514` unspecified-encoding, `D417` undocumented-param, `ASYNC110` async-busy-wait, `ASYNC230` blocking-open-call-in-async-function, `S603` subprocess-without-shell-equals-true, `DTZ005` call-datetime-now-without-tzinfo, `T201` print, `RUF006` asyncio-dangling-task.

Python 3.15 als Ziel: `ruff check --target-version py315`, `ty check --python-version 3.15`, `pyright --pythonversion 3.15` liefen alle ohne Fehler.

---

## Quellcode-Stellen (ohne eigenen Lauf)

| Paket | Datei | Befund |
|---|---|---|
| icmplib 3.0.4 | `icmplib/sockets.py` Z. 81–97 | `self._privileged = privileged or PLATFORM_WINDOWS` → unter Windows immer `SOCK_RAW`; Fehlercode 10013 wird zu `SocketPermissionError` |
| icmplib 3.0.4 | `icmplib/ping.py`, `async_ping` | Schleife: `sleep(interval)` → senden → `await sock.receive(request, timeout)`; also sequentiell |
| icmplib 3.0.4 | `icmplib/models.py`, `jitter` | Mittel der absoluten Differenzen aufeinanderfolgender RTTs |
| icmplib 3.0.4 | `README.md` | zu `privileged`: „Only available on Unix systems. Ignored on Windows.“ |
| dnspython 2.9.2 | `dns/win32util.py` | System-DNS unter Windows aus der Registry (`NameServer`, `DhcpNameServer`), optional über WMI |
| dnspython 2.9.2 | `dns/_asyncio_backend.py` | eigene Behandlung für `win32` (explizites Binden vor `recvfrom`) |
