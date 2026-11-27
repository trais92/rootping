# ADR-012: Bei VPN den Heimrouter messen und DNS nur über den VPN-DNS

- **Status:** vorgeschlagen (Sprint 1, von Claude im Rahmen der freigegebenen Autonomie getroffen; Kai prüft im Review)
- **Datum:** 2026-11-27

## Kontext
Kais Windows-Test mit aktivem NordVPN zeigte: Die Router-Erkennung über `GetBestRoute` lieferte das VPN-Gateway (`10.5.0.1`) statt der FritzBox, der Adapter hieß `iftype53_32769`, und alle DNS-Ziele meldeten `timeout`, weil NordVPN DNS an fremde Server blockiert. Ohne Änderung hätten VPN-Nutzer dauerhafte Fehlalarme und keine Aussage über ihr Heimnetz.

## Entscheidung
1. **Heimrouter statt VPN-Gateway:** Das Betriebssystem-Modul liefert alle verbundenen Karten (Name, Gateway, Metrik, Tunnel ja/nein, DNS-Server) und die aktive Karte. Eine reine Funktion `choose_network` wählt daraus den Router der bevorzugten Karte **ohne** Tunnel und merkt sich das VPN getrennt (`NetworkContext.vpn`). Regeln: [netzwerk.md](../netzwerk.md).
2. **Lesbare Namen:** Windows-Karten heißen wie in den Windows-Einstellungen (`FriendlyName` aus `GetAdaptersAddresses`).
3. **VPN gehört zum Kontext:** `network_contexts` ist eindeutig über `(gateway, interface, vpn)`. VPN an/aus ist ein Netzwechsel.
4. **DNS `system` = DNS der aktiven Karte** (Windows), sonst wie bisher der erste System-DNS.
5. **Bei aktivem VPN misst `dns_lookup` nur `system`** (Einstellung `only_system_with_vpn = true`, abschaltbar).
6. **Gesperrte Antworten:** Antwortet ein DNS-Server mit `0.0.0.0`/`127.0.0.1` (Pi-hole o. Ä. sperrt den Testnamen), wird das als Fehlercode `blocked` gespeichert, mit Antwortzeit.

## Betrachtete Alternativen
- **Weiter den Weg ins Internet messen (VPN-Gateway):** misst den Tunnel statt des Heimnetzes; das Ziel „WLAN/LAN in Ordnung?“ ginge verloren.
- **Bei VPN gar nicht messen:** einfach, aber Gaming über VPN ist gerade ein Fall, den Kai messen will.
- **Zusätzliches Ziel „Resolver des Betriebssystems“ (`getaddrinfo`):** Windows und systemd-resolved beantworten wiederholte Anfragen aus ihrem Zwischenspeicher; die Antwortzeit wäre fast immer 0 ms und sagt nichts. Der DNS-Server der aktiven Karte ist genau der, den dieser Resolver fragt; ihn direkt zu messen ist aussagekräftiger.
- **Bei VPN Router-DNS und 1.1.1.1 weiter messen und `timeout` als „VPN-bedingt“ markieren:** Raten, ob ein Timeout vom VPN oder einer Störung kommt, ist genau das, was RootPing vermeiden soll.
- **Migration 002 statt Änderung von 001:** Sprint 1 ist noch nicht gemergt, es gibt keine Datenbanken außer Testdateien. Eine Migration hätte einen Tabellen-Umbau mit abgeschalteten Fremdschlüsseln gebraucht, für keinen Nutzen.

## Konsequenzen
- `ping_gateway` misst auch bei VPN das Heimnetz. Blockiert ein VPN den Zugriff aufs lokale Netz, zeigt sich das als Verlust; `rootping check` macht das sichtbar.
- Mit VPN fehlt der DNS-Vergleich Router vs. öffentlich; dafür gibt es keine Fehlalarme.
- Datenbanken aus Testläufen vor dieser Änderung passen nicht mehr zum Schema und müssen gelöscht werden.
- Die Tunnel-Erkennung ist eine Heuristik (Adaptertyp, Beschreibung). Unbekannte VPN-Adapter gelten als normale Karte; dann verhält sich RootPing wie vor dieser Änderung.
