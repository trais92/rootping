# ADR-002: Windows und Linux, Labor nur unter Linux

- **Status:** angenommen
- **Datum:** 2026-11-26

## Kontext
RootPing soll auf den Rechnern laufen, auf denen Leute tatsächlich Netzprobleme haben, also vor allem Windows. Gleichzeitig braucht die Störungssimulation `tc netem`, das es nur unter Linux gibt. Der erste Planentwurf sah nur Linux vor; Kai hat Windows als Pflicht festgelegt.

## Entscheidung
RootPing (Messungen, Erkennung, Agent, MCP) läuft auf **Windows und Linux**. Das **Störungslabor läuft nur in Linux-Containern** (unter Windows über Docker Desktop / WSL2). Betriebssystem-spezifisches steckt im Modul `platform/` (`windows.py`, `linux.py`). Die CI testet jeden PR auf beiden Systemen.

## Betrachtete Alternativen
- **Nur Linux:** weniger Aufwand, aber am Zielpublikum vorbei.
- **Zusätzlich macOS:** noch eine Plattform mit eigenen Befehlen und eigener CI, ohne Mehrwert für die Kernidee. Später möglich.

## Konsequenzen
- Etwa 4–6 Stunden Mehraufwand, vor allem in Sprint 1 (CI, Gateway-Erkennung, Ping-Spike).
- Systembefehle (z. B. `tracert`) liefern je nach Sprache andere Texte: nur Zahlen und IPs auswerten, mit deutschen und englischen Beispielen testen.
- Pfade über `platformdirs`, nie fest verdrahtet.
