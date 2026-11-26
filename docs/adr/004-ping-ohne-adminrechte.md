# ADR-004: Ping ohne Adminrechte mit icmplib

- **Status:** angenommen, wird in Sprint 1 durch einen Spike bestätigt
- **Datum:** 2026-11-26

## Kontext
Ping braucht klassisch Raw Sockets, also Admin- bzw. Root-Rechte. RootPing soll ohne Adminrechte im Hintergrund laufen, auf Windows und Linux, und für Gaming jede Sekunde messen.

## Entscheidung
Ping über die Bibliothek **`icmplib`** mit `privileged=False` (asynchron, `async_ping`). Ob das unter Windows zuverlässig klappt, prüft ein kurzer Spike am Anfang von Sprint 1.

**Plan B**, falls der Spike scheitert: die Ping-Probe ruft den System-`ping` auf und liest nur die Zahlen aus der Ausgabe.

## Betrachtete Alternativen
- **System-`ping` aufrufen:** funktioniert überall ohne Admin, aber pro Messung ein neuer Prozess, Ausgabe je nach System und Sprache verschieden. Deshalb nur Plan B.
- **TCP-Verbindungszeit statt Ping:** braucht keine Rechte, misst aber etwas anderes (und nicht jeder Router hat einen offenen Port).

## Konsequenzen
- Unter Linux muss `net.ipv4.ping_group_range` den Benutzer erlauben (bei den meisten Distributionen Standard); das steht in der Installationsanleitung.
- Ein Wechsel auf Plan B betrifft nur die Ping-Probe, weil der Rest nur `measure()` kennt.
