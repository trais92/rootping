# ADR-005: Traceroute nur auf Anfrage

- **Status:** angenommen
- **Datum:** 2026-11-26

## Kontext
Mit Router-Ping und Internet-Pings lässt sich „Heimnetz“ von „dahinter“ trennen, aber nicht „Provider“ von „weiter hinten im Internet“. Traceroute kann das. Es ist aber langsam (oft 15–30 s), belastet fremde Router und wird leicht falsch gedeutet, weil viele Router Traceroute absichtlich langsam beantworten.

## Entscheidung
Traceroute läuft **nur auf Anfrage**: per `rootping trace <ziel>`, über das MCP-Werkzeug `traceroute_now` oder als Werkzeug des Agenten bei einer Störung. Nie dauerhaft im Hintergrund. Umsetzung über den System-Befehl ohne Adminrechte (`tracert -d` bzw. `traceroute -n`, sonst `tracepath -n`), höchstens 1 pro Minute.

## Betrachtete Alternativen
- **Regelmäßig im Hintergrund (z. B. alle 15 min):** liefert Verlauf, kostet aber Last und Daten, die fast nie gebraucht werden.
- **Gar kein Traceroute:** einfacher, aber die Diagnose bleibt bei „Provider oder Internet“ ungenau.

## Konsequenzen
- Der Agent entscheidet selbst, wann er tiefer gräbt. Die Auswertung zählt, wie oft und ob es geholfen hat.
- Die Regel-Baseline nutzt kein Traceroute (bewusst, siehe `docs/diagnose.md`, Abschnitt Fairness).
- Deutungsregel: Verlust an einem Zwischen-Hop zählt nur, wenn er bis zum Ziel anhält.
