# ADR-006: Ping über die Schnittstellen des Betriebssystems, mit festem Takt

- **Status:** angenommen (2026-11-27, Kai), ersetzt [ADR-004](004-ping-ohne-adminrechte.md)
- **Datum:** 2026-11-26

## Kontext
ADR-004 sah `icmplib` mit `privileged=False` auf beiden Systemen vor. Die Recherche ([tech-stack.md](../tech-stack.md), Befunde B1–B3) hat drei Probleme gezeigt:

1. **Windows:** `icmplib` ignoriert `privileged=False` und öffnet immer einen Raw Socket (`sockets.py`: `self._privileged = privileged or PLATFORM_WINDOWS`). Raw Sockets erfordern unter Windows Administratorrechte (Microsoft-Doku „TCP/IP Raw Sockets“). `ping.exe` nutzt stattdessen die ICMP-API `IcmpSendEcho2` aus `Iphlpapi.dll`, die keine besonderen Rechte braucht.
2. **Takt:** `icmplib.async_ping(count=N)` wartet nach jedem Paket auf Antwort oder Timeout. Bei Verlust dauert eine Runde mit 10 Paketen bis zu 29 s statt etwa 11 s (Test T3). Gerade bei Störungen würden die Zeitfenster der Erkennung falsch.
3. **Linux:** Unprivilegierter Ping braucht `net.ipv4.ping_group_range`; Kernel-Standard ist `1 0` (niemand darf), erst systemd setzt einen offenen Bereich.

## Entscheidung
Ein eigenes Modul `rootping/net/icmp.py` mit einer Funktion `echo(target, timeout) -> float | None` pro Betriebssystem:

- **Linux:** ICMP-Datagram-Socket über `icmplib` (`async_ping(count=1, privileged=False)`).
- **Windows:** `IcmpSendEcho2` über `ctypes` (Standardbibliothek), aufgerufen mit `asyncio.to_thread`.

Darüber sendet ein **Takt-Treiber** pro Ziel jede Sekunde ein Echo, ohne auf Antworten zu warten, und ordnet die Ergebnisse nach Sendezeitpunkt einer 10-s-Runde zu. Mittelwert, Maximum, Verlust und Jitter berechnet RootPing **selbst** in einer reinen Funktion (`summarize`). Jitter = Mittel der absoluten Differenzen aufeinanderfolgender Laufzeiten; verlorene Pakete werden übersprungen.

Beim Start prüft RootPing unter Linux `ping_group_range` und gibt bei Bedarf eine verständliche Meldung mit Abhilfe aus.

## Betrachtete Alternativen
- **`icmplib` auf beiden Systemen:** scheitert unter Windows ohne Admin.
- **System-`ping` aufrufen:** ein Prozess pro Echo (3–4 pro Sekunde), Ausgabe sprachabhängig. Bleibt als Notlösung dokumentiert.
- **Bibliothek `ipscout`:** macht technisch das Richtige, ist aber erst seit Juli 2026 auf PyPI, mit einem Maintainer. Zu riskant für den Kern des Projekts.
- **`ping3`, `winping`:** dasselbe Rechteproblem bzw. seit 2019 nicht gepflegt.
- **Bei `async_ping(count=10)` bleiben und die Konfiguration anpassen:** liefert bei Verlust unregelmäßige Zeitfenster.

## Konsequenzen
- RootPing läuft unter Windows wie `ping.exe`: ohne Admin, ohne Unterprozess, ohne Textauswertung.
- Unter Windows liefert die API ganze Millisekunden; Laufzeiten unter 1 ms erscheinen als 0 (wie „<1ms“ bei `ping.exe`). Für die Schwellen (10 ms Router, 60 ms Internet) unerheblich.
- Die Statistik ist auf beiden Systemen identisch definiert und ohne Netzwerk testbar (Hypothesis).
- Die Konfiguration in `probes.md` ändert sich (`count`/`packet_interval` entfallen zugunsten „1 Echo pro Sekunde, Runde = 10 s“).
- Der Windows-Weg ist noch nicht selbst getestet. Der Spike am Anfang von Sprint 1 läuft auf Kais PC **ohne erhöhte Rechte**, weil GitHub-Windows-Runner als Administrator laufen und dort auch der falsche Weg funktionieren würde.
- `icmplib` wird nur noch für einen einzigen Aufruf unter Linux genutzt (letztes Release 10/2023). Ein Ersatz durch eigenen Socket-Code beträfe nur `icmp.py`.
