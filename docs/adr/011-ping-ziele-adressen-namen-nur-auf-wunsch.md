# ADR-011: Ping- und DNS-Ziele sind IPv4-Adressen; Namen nur auf Wunsch

- **Status:** angenommen (Kai, 27.11.2026, mit Änderung: Namen als Opt-in)
- **Datum:** 2026-11-27

## Kontext
Die Konfiguration nennt Ziele wie `1.1.1.1`. Offen war, ob auch Namen wie `www.ea.com` erlaubt sind. Die Windows-ICMP-API braucht eine Adresse. Kai möchte aber gezielt Websites und Spieldienste testen können, deren Adresse man nicht kennt oder die wechselt.

## Entscheidung
1. **Standard: nur IPv4-Adressen.** Ping-Ziele (`ping_gateway`, `ping_internet`) und DNS-Server (`dns_lookup`) sind IPv4-Adressen, plus die Platzhalter `auto` (Router) bzw. `gateway`/`system`. Geprüft wird beim Start durch die Pydantic-Modelle und zusätzlich in `net/icmp.echo()`.
2. **Opt-in für Namen bei `ping_internet`:** Mit `allow_hostnames = true` dürfen dort auch Hostnamen stehen (z. B. `www.ea.com`, ohne `https://`).
   - Der Name wird **vor jeder Runde** über den Resolver des Betriebssystems übersetzt (`net/resolve.py`, `getaddrinfo`), also so wie im Browser oder im Spiel.
   - Klappt die Übersetzung nicht, wird die Runde mit `error = "resolve_failed"` gespeichert, **ohne** Verlust-Wert. Eine DNS-Störung sieht so nie wie Paketverlust aus.
   - Gespeichert wird der Name als `target`, damit die Messreihe zusammenbleibt, auch wenn die Adresse wechselt. Die jeweils aufgelöste Adresse steht im Debug-Log.
3. `ping_gateway` und `dns_lookup` bleiben immer bei Adressen: Ein Router oder DNS-Server per Name ergibt keinen Sinn, weil man DNS bräuchte, um DNS zu messen.

## Betrachtete Alternativen
- **Nur Adressen, ohne Ausnahme** (ursprünglicher Vorschlag): am saubersten, aber Kai kann dann eine bestimmte Website nicht gezielt testen.
- **Namen immer erlauben:** Tippfehler fallen nicht mehr beim Start auf, und unbemerkt hinge jede Ping-Messung vom DNS ab.
- **Namen einmal beim Start auflösen:** versteckt, dass die Adresse wechseln kann (CDNs), und eine spätere DNS-Störung bliebe unsichtbar.
- **Opt-in pro einzelnem Ziel** (z. B. `"name:www.ea.com"`): feiner, aber eine eigene Schreibweise, die man kennen muss. Ein Schalter pro Probe ist einfacher und reicht, weil die Standardziele Adressen sind.
- **IPv6 gleich mit erlauben:** nicht in v1 (siehe [ping.md](../ping.md)).

## Konsequenzen
- Ohne Opt-in misst Ping nur die Leitung und DNS nur DNS; die Regel-Baseline kann beides sauber trennen.
- Mit Opt-in hängt das Ergebnis eines Namensziels auch vom DNS ab; das ist dann sichtbar (`resolve_failed`), nicht versteckt.
- Hinter einem Namen können über die Zeit verschiedene Server stehen (CDN). Schwankungen können daher auch vom Serverwechsel kommen.
- Das Zeitlimit einer Runde im Scheduler ist `interval + 2 × timeout` (ein `timeout` für die Namensauflösung).
