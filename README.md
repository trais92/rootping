# RootPing

Ein schlankes Netzwerk-Diagnose-Tool mit KI-Agent. RootPing misst Ping (Router und Internet) und DNS, speichert die Werte in SQLite und lässt einen Claude-Agenten Störungen erkennen und erklären.

Über simulierte Netzwerkfehler (netem) wird verglichen, wie gut die KI gegenüber festen Regeln abschneidet.

> Status: Planungsphase, noch kein Code. Technische Grundlage: [docs/tech-stack.md](docs/tech-stack.md).

## Voraussetzungen (geplant)

- **Windows:** keine Adminrechte nötig, Ping läuft über die eingebaute Windows-ICMP-API.
- **Linux:** Ping ohne root braucht die Kernel-Einstellung `net.ipv4.ping_group_range`, die die eigene Gruppe einschließt. Auf vielen Systemen (mit systemd) ist das schon so. Prüfen mit `sysctl net.ipv4.ping_group_range`.
