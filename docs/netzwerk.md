# Netzwerk erkennen: Heimrouter, VPN und DNS-Server

> Stand 27.11.2026 · Code: `src/rootping/platform/common.py` (Entscheidung), `platform/windows.py` und `platform/linux.py` (Rohdaten) · Entscheidung: [ADR-012](adr/012-vpn-heimrouter-und-vpn-dns.md)

## Kurz gesagt

Vor jeder Messrunde fragt RootPing das Betriebssystem: Welche Netzwerkkarten gibt es, welche hat einen Router, welche ist ein VPN, und über welche Karte läuft der Internetverkehr gerade? Daraus entsteht ein **Netzwerk-Kontext** (`NetworkContext`):

| Feld | Beispiel ohne VPN | Beispiel mit NordVPN |
|---|---|---|
| `gateway` (Heimrouter) | `192.168.178.1` | `192.168.178.1` (nicht das VPN-Gateway `10.5.0.1`) |
| `interface` (Karte zum Heimrouter) | `Ethernet 2` | `Ethernet 2` |
| `vpn` (VPN-Karte oder leer) | `""` | `NordLynx` |
| `dns_servers` (DNS der aktiven Karte) | `192.168.178.1` | DNS-Server von NordVPN |

`ping_gateway` pingt immer den **Heimrouter**, auch bei aktivem VPN. So bleibt die Frage „Ist mein WLAN/LAN in Ordnung?“ beantwortbar, egal ob ein VPN läuft.

## Warum das nötig ist (Befund aus dem Windows-Test)

Im ersten Windows-Test mit aktivem NordVPN nahm RootPing den Weg, den Windows für Pakete ins Internet wählt. Das war der NordLynx-Tunnel. Folgen:

1. Als „Router“ erschien das VPN-Gateway `10.5.0.1` statt der FritzBox. Gemessen wurde also der VPN-Tunnel, nicht das Heimnetz.
2. Der Adapter hieß `iftype53_32769` (interner Windows-Name) statt eines lesbaren Namens.
3. Alle DNS-Ziele meldeten `timeout`, weil NordVPN DNS-Anfragen an fremde Server blockiert. Das wäre ein dauerhafter Fehlalarm gewesen.

## Die Regeln (`choose_network`)

Die Entscheidung ist eine reine Funktion ohne Zugriff auf das System. Sie wird in `tests/test_network_choice.py` mit nachgebauten Rechnern geprüft, auf jedem Betriebssystem.

1. **Aktive Karte:** die Karte, über die ein Paket ins Internet ginge. Ist sie ein Tunnel, ist ein VPN aktiv (`vpn` = ihr Name).
2. **Heimrouter:** das Gateway der aktiven Karte, wenn sie kein Tunnel ist. Sonst das Gateway der Karte ohne Tunnel mit der kleinsten Routing-Metrik.
3. **Nur Tunnel:** Gibt es keine Karte ohne Tunnel mit Gateway, wird das Gateway der aktiven Karte genommen. Ohne jedes Gateway gibt es kein Netz (`None`, Fehler `no_gateway`).
4. **DNS-Server:** die der aktiven Karte (bei VPN also die des VPN), sonst die der Heimrouter-Karte.

Zwei Kontexte gelten als gleich, wenn Router, Karte und VPN gleich sind. Die DNS-Server zählen dafür nicht, weil sie sich auch ohne Netzwechsel ändern können (z. B. per DHCP). VPN an oder aus ist also ein Netzwechsel: Es entsteht ein Ereignis `network_change` und ein eigener Eintrag in `network_contexts`. Die spätere Störungserkennung vergleicht so keine Messungen mit und ohne VPN.

## Woher die Rohdaten kommen

### Windows

| Was | Quelle |
|---|---|
| Karten, lesbarer Name (`FriendlyName`, z. B. „Ethernet 2“), Typ, Gateway, DNS-Server, Metrik | `GetAdaptersAddresses` aus `Iphlpapi.dll` |
| Aktive Karte | `GetBestRoute` zu `1.1.1.1` (es wird kein Paket gesendet) |
| Tunnel? | Adaptertyp 53 (`IF_TYPE_PROP_VIRTUAL`: NordLynx, WireGuard, Wintun), 23 (PPP), 131 (Tunnel), oder die Beschreibung enthält z. B. „TAP-Windows“, „WireGuard“, „OpenVPN“, „VPN“ (TAP-Adapter geben sich als Ethernet aus) |

Nur Karten mit Status „verbunden“ zählen, Loopback wird ignoriert. Beides braucht keine Adminrechte.

### Linux

| Was | Quelle |
|---|---|
| Karten | `socket.if_nameindex()` (ohne `lo`) |
| Gateway und Metrik je Karte | `/proc/net/route` (Standardrouten) |
| Aktive Karte | Ein UDP-Socket wird mit `1.1.1.1` „verbunden“ (kein Paket). Der Kernel wählt dabei die Absenderadresse nach allen Routing-Regeln, auch nach den eigenen Tabellen von WireGuard. Die Karte mit dieser Adresse ist die aktive. |
| Tunnel? | `/sys/class/net/<karte>/type` ist ein Tunnel-Typ (z. B. 65534 für tun und WireGuard, 512 für PPP) oder die Datei `tun_flags` existiert (tun/tap) |
| DNS-Server | Linux liefert sie nicht einfach pro Karte; `dns_servers` bleibt leer. DNS `system` nimmt dann `/etc/resolv.conf` ([dns.md](dns.md)). |

Alles ohne Unterprozess und ohne root.

## Was das für die Messungen heißt

- **`ping_gateway`** pingt den Heimrouter. Manche VPNs verbieten den Zugriff aufs lokale Netz (bei NordVPN: Einstellung „Im lokalen Netzwerk unsichtbar“). Dann meldet `ping_gateway` Verlust, solange das VPN läuft. Das ist dann eine Einstellung, keine Störung; in `rootping check` sieht man es sofort.
- **`ping_internet`** läuft bei aktivem VPN durch den Tunnel und misst damit die Verbindung inklusive VPN.
- **`dns_lookup`** misst bei aktivem VPN standardmäßig nur den VPN-DNS ([dns.md](dns.md#vpn)).
- **`rootping check`** zeigt Router, Karte, VPN und DNS-Server an.

## Grenzen

- Nur IPv4 (wie überall in v1).
- Split-Tunnel-VPNs, die nur einzelne Ziele umleiten, sehen für RootPing wie „kein VPN“ aus, weil der Weg zu `1.1.1.1` nicht durch den Tunnel geht. Das ist richtig: Dann misst RootPing auch nicht durch den Tunnel.
- Unternehmens-VPNs mit ungewöhnlichen Adaptern, die weder am Typ noch an der Beschreibung erkennbar sind, gelten als normale Karte. Abhilfe wäre eine Liste in der Konfiguration; bewusst erst, wenn das jemand braucht.
