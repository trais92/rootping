# ADR-011: Ping- und DNS-Ziele sind IPv4-Adressen, keine Namen

- **Status:** vorgeschlagen (Sprint 1, von Claude im Rahmen der freigegebenen Autonomie getroffen; Kai prüft im Review)
- **Datum:** 2026-11-27

## Kontext
Die Konfiguration nennt Ziele wie `1.1.1.1`. Offen war, ob auch Namen wie `dns.google` erlaubt sind. `icmplib` würde Namen selbst auflösen; die Windows-ICMP-API braucht eine Adresse.

## Entscheidung
Ping-Ziele (`ping_gateway`, `ping_internet`) und DNS-Server (`dns_lookup`) müssen **IPv4-Adressen** sein, plus die Platzhalter `auto` (Router) bzw. `gateway`/`system`. Geprüft wird beim Start durch die Pydantic-Modelle und zusätzlich in `net/icmp.echo()`.

## Betrachtete Alternativen
- **Namen erlauben und vor jeder Runde auflösen:** Eine DNS-Störung sähe dann aus wie 100 % Paketverlust im Internet. Genau diese Unterscheidung (Leitung oder DNS?) soll RootPing aber treffen. Zudem wechselt die Adresse hinter einem Namen, die Messreihe wäre nicht vergleichbar.
- **Namen einmal beim Start auflösen:** vermeidet das Problem während des Betriebs, verschiebt es aber auf den Start und versteckt, welche Adresse tatsächlich gemessen wird.
- **IPv6 gleich mit erlauben:** nicht in v1 (siehe [ping.md](../ping.md)); die Prüfung lässt sich später an einer Stelle erweitern.

## Konsequenzen
- Ping misst nur die Leitung, DNS misst nur DNS. Die Regel-Baseline kann beides sauber trennen.
- Tippfehler oder Namen fallen beim Start mit klarer Meldung auf.
- Wer einen Spielserver messen will, trägt dessen Adresse ein, nicht den Namen.
