# DNS-Messung

> Stand 27.11.2026 · Code: `src/rootping/probes/dns.py`, `net/dns_query.py` · Hintergrund: [tech-stack.md](tech-stack.md) 3.10, [diagnose.md](diagnose.md)

## Kurz gesagt

Alle 30 Sekunden fragt `dns_lookup` jeden eingestellten DNS-Server einmal nach dem A-Eintrag von `example.com` und speichert Antwortzeit oder Fehlerart. Damit lässt sich „Internet geht, aber Seiten laden nicht“ (DNS kaputt) von einer Leitungsstörung unterscheiden.

## Ziele

| Ziel in der Konfiguration | Bedeutung | Gespeichert als |
|---|---|---|
| `gateway` | Anfrage direkt an den Router (die meisten Heimrouter leiten DNS weiter) | Router-IP |
| `system` | DNS-Server, den das System gerade benutzt: Windows den der aktiven Netzwerkkarte (bei VPN der VPN-DNS), Linux den ersten aus `/etc/resolv.conf` | dessen IP |
| `1.1.1.1` | öffentlicher Server als Vergleich | `1.1.1.1` |

- Platzhalter werden **vor jeder Runde** neu übersetzt (Netzwechsel).
- Zeigen zwei Ziele auf dieselbe Adresse (oft ist der System-DNS der Router), wird sie **einmal** gemessen.
- Ob eine Zeile den Router-DNS betrifft, sieht man am Vergleich `measurements.target = network_contexts.gateway`.
- Unter Linux mit systemd-resolved ist `system` meist `127.0.0.53`, also der lokale Zwischenspeicher. Genau deshalb gibt es zusätzlich `gateway` (Entscheidung E7).

## VPN

Viele VPNs (z. B. NordVPN) lassen DNS-Anfragen nur an ihre eigenen Server durch. Router-DNS und `1.1.1.1` meldeten im Windows-Test deshalb jede Runde `timeout`, obwohl alles funktionierte. Darum gilt:

- Ist ein VPN aktiv ([netzwerk.md](netzwerk.md)), misst `dns_lookup` nur `system`, also den DNS-Server des VPN.
- Abschalten mit `only_system_with_vpn = false`, falls das eigene VPN fremde DNS-Server erlaubt.

Begründung und Alternativen: [ADR-012](adr/012-vpn-heimrouter-und-vpn-dns.md).

## Fehlerarten

| `error` | Bedeutung |
|---|---|
| `timeout` | Keine Antwort innerhalb von `timeout` Sekunden |
| `nxdomain` | Server sagt, den Namen gibt es nicht (bei `example.com` ein Zeichen für Fehlkonfiguration oder Umleitung) |
| `noanswer` | Name existiert, aber ohne A-Eintrag |
| `servfail` | Server meldet einen Fehler (SERVFAIL, REFUSED) |
| `dns_error` | Sonstiger DNS-Fehler |
| `blocked` | Antwort kam, zeigt aber nur auf `0.0.0.0` bzw. `127.0.0.1`: Ein Werbeblocker wie Pi-hole sperrt den Testnamen. Der Server funktioniert (die Antwortzeit wird trotzdem gespeichert), aber die Messung sagt nichts über eine echte Auflösung. Abhilfe: `query` in der Konfiguration auf einen nicht gesperrten Namen ändern. `rootping check` zeigt dazu eine Warnung. |
| `no_gateway` / `no_system_dns` | Platzhalter ließ sich nicht übersetzen (kein Router bzw. kein System-DNS) |

## Wie gemessen wird

Pro Abfrage legt `net/dns_query.py` einen eigenen `dnspython`-Resolver an, mit genau **einem** Nameserver und **ohne Cache**. So ist eindeutig, welcher Server wie schnell geantwortet hat. Die Antwortzeit enthält eventuelle Wiederholungen von dnspython innerhalb des Timeouts.

**Grenze:** Wer alle 30 s denselben Namen abfragt, misst meist den Cache des Routers bzw. Resolvers. Das beantwortet die Frage „antwortet DNS überhaupt und schnell?“, nicht „wie schnell löst der Provider neue Namen auf?“ ([diagnose.md](diagnose.md)).

## Tests

`tests/test_dns.py` startet einen kleinen DNS-Server auf `127.0.0.1`, der wahlweise normal, mit `0.0.0.0` (wie Pi-hole), mit NXDOMAIN, mit SERVFAIL oder gar nicht antwortet. So werden alle Fehlerarten echt geprüft, ohne Internet.
