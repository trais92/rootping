# RootPing – Projektplan (Lite-Version)

> Stand: 26.11.2026 · Entwurf für Sprint 0 · ersetzt den ursprünglichen „layerwatch“-Plan
> Umfang: 5 Sprints à 1 Woche, ca. 10 Stunden pro Sprint, plus Sprint 0 (Theorie)

**Pitch:** *„Mein Agent findet heraus, warum dein Internet hakt, und ich habe gemessen, wie oft er recht hat.“*

---

## 1. Ziel

**Problem:** „Das Internet hakt“, aber woran liegt es? Am Router, am Provider oder am DNS? Ohne Messdaten bleibt nur Raten.

**Lösung:** RootPing misst im Hintergrund wenige, aussagekräftige Werte, speichert sie in SQLite und erkennt Störungen. Bei einer Störung grenzt ein Claude-Agent die Ursache Schicht für Schicht ein und belegt jede Aussage mit Messwerten. Über einen MCP-Server kann man dieselben Daten aus Claude Desktop oder Claude Code heraus befragen.

**Das Herzstück:** Eine Störungssimulation (Docker + `tc netem`) erzeugt Fehler mit bekannter Ursache. Damit wird gemessen, wie oft der KI-Agent die richtige Ursache findet, im Vergleich zu einem einfachen regelbasierten Entscheidungsbaum.

**Was das Projekt in Bewerbungen zeigt:**
- Agent mit Werkzeugen (Tool Use) und MCP-Server praktisch umgesetzt
- KI wird **nicht blind vertraut**, sondern mit einer Auswertung gegen eine Baseline geprüft
- Strukturierte Fehlereingrenzung wie im IT-Betrieb
- Saubere Projektarbeit: Plan, Entscheidungen (ADRs), Tests, CI auf Windows und Linux

> **Warum so schlank?** Der Originalplan hatte 8 Sprints, 5 Schichten, 3 Betriebssysteme und ein Dashboard. Die Lite-Version behält Windows und Linux, streicht den Rest. Für eine Bewerbung zählt, dass das Projekt *fertig* ist und in 2 Minuten verstanden wird. Die Auswertung „KI vs. Regeln“ ist das, was es von hundert anderen Ping-Tools unterscheidet. Alles andere ist Beiwerk.

---

## 2. Umfang

| In v1 | Nicht in v1 (bewusst gestrichen) |
|---|---|
| Ping zum Router (Gateway automatisch erkannt) | WLAN-Werte (stark plattformabhängig) |
| Ping zu 2–3 Internet-Zielen | macOS, Autostart als Dienst (Windows wie Linux) |
| DNS-Abfragen gegen System-DNS und einen öffentlichen DNS | Dauerhaftes Traceroute, HTTPS-Prüfungen, ARP-Geräteliste |
| Traceroute **auf Anfrage** (CLI, MCP, Agent) | |
| Gaming-taugliche Messung: 1 Ping/s, Maximalwert, absolute Schwellen | |
| SQLite-Speicherung | Dashboard (stattdessen CLI) |
| Störungserkennung mit festen Schwellwerten | Normalwerte nach Tageszeit (braucht Wochen an Daten) |
| Regel-Baseline (Entscheidungsbaum) | Wochenbericht, Desktop-Benachrichtigungen |
| Claude-Agent mit Werkzeugen | Releases für alle Systeme |
| MCP-Server (gleiche Werkzeuge) | |
| Störungslabor (Docker + netem) und Auswertung | |

Zielplattformen: **Windows und Linux**. RootPing selbst (Messungen, Erkennung, Agent, MCP) läuft auf beiden. Das Störungslabor bleibt in Linux-Containern, denn `tc netem` gibt es nur unter Linux; unter Windows läuft es über Docker Desktop (WSL2).

**Was Windows konkret bedeutet:**
- Plattformabhängiges ist in einem kleinen Modul gekapselt (`platform/windows.py`, `platform/linux.py`). Das betrifft vor allem die **Gateway-Erkennung** (Linux: Routing-Tabelle, Windows: `Get-NetRoute` bzw. `route print`).
- **Ping ohne Adminrechte** muss auf Windows früh geprüft werden (kurzer Spike in Sprint 1). Plan B: System-`ping` aufrufen oder TCP-Verbindungszeit messen.
- Dateipfade (Datenbank, Konfiguration) über `platformdirs`, nicht fest verdrahtet.
- CI testet jeden PR auf **Windows und Linux**.

---

## 3. Messungen

| Messung | Was | Intervall (Vorschlag) | Bibliothek |
|---|---|---|---|
| `ping_gateway` | Latenz (Mittel und Maximum), Paketverlust, Jitter zum Router | 1 Ping/s, zusammengefasst alle 10 s | `icmplib` (ohne Root möglich) |
| `ping_internet` | dasselbe zu 2–3 Zielen (z. B. 1.1.1.1, 9.9.9.9) | 1 Ping/s, zusammengefasst alle 10 s | `icmplib` |
| `dns_lookup` | Antwortzeit, Erfolg, Fehlerart (Timeout, SERVFAIL, NXDOMAIN) pro DNS-Server | 30 s | `dnspython` |

**Warum genau diese drei?** Sie reichen für die wichtigste Unterscheidung: *Heimnetz kaputt* (Router-Ping schlecht) vs. *Provider/Internet kaputt* (Router gut, Internet schlecht) vs. *DNS kaputt* (Pings gut, DNS schlecht). Mehr Messungen machen den Agenten nicht klüger, nur das Projekt größer.

**Auch fürs Gaming:** Jeder Wert, der nicht dem guten Zustand entspricht, wird markiert, z. B. schon ein Ping über 60 ms oder ein einzelnes verlorenes Paket. Dafür gibt es zwei Stufen, *Auffälligkeit* und *Störung*, mit absoluten, konfigurierbaren Schwellen. Details in [diagnose.md](diagnose.md).

**Traceroute auf Anfrage:** per `rootping trace`, über MCP oder als Werkzeug des Agenten bei einer Störung. Nie dauerhaft im Hintergrund, weil es langsam ist und fremde Router belastet.

Jede Messung speichert zusätzlich den **Netzwerk-Kontext** (Gateway-IP, Interface). So lässt sich ein Netzwechsel (anderes WLAN, VPN an) von einer echten Störung unterscheiden.

---

## 4. Architektur

```mermaid
flowchart LR
  subgraph rp["RootPing"]
    probes["Messungen<br>(Plugins)"]
    db[("SQLite")]
    detect["Störungserkennung<br>(Schwellwerte)"]
    tools["Werkzeuge<br>(gemeinsam)"]
    rules["Regel-Baseline"]
    agent["Claude-Agent"]
    mcp["MCP-Server"]
  end
  net(("Router · Internet · DNS<br>oder Labor"))
  claude[("Claude API")]
  client["Claude Desktop / Code"]

  probes --> net
  probes --> db --> detect
  detect -- Vorfall --> rules
  detect -- Vorfall --> agent
  agent --> tools --> db
  agent --> claude
  client -- MCP --> mcp --> tools
```

**Kernideen**
1. **Messungen sind austauschbare Plugins** mit gemeinsamer Schnittstelle. Wichtig für das Labor: Dieselben Messungen laufen gegen das echte Netz oder gegen die Container, nur die Ziele kommen aus der Konfiguration.
2. **Erst Regeln, dann KI.** Die Erkennung „da stimmt was nicht“ ist simple Statistik ohne KI. Claude wird nur gefragt, *warum*. Das ist günstig, testbar und nachvollziehbar.
3. **Ein Werkzeugsatz, zwei Nutzer.** Agent und MCP-Server rufen dieselben Python-Funktionen auf (z. B. `get_recent_measurements`, `get_incident`, `ping_now`, `dns_lookup_now`).
4. **Diagnose als strukturierte Antwort:** betroffene Schicht, Ursache, Belege (Messwerte), Sicherheit, Empfehlung. Nur so kann man KI und Regeln automatisch vergleichen.
5. **Leicht änderbar (Grundregel von Kai).** Kleine Module mit klaren Schnittstellen, keine fest verdrahteten Werte (Ziele, Intervalle, Schwellwerte, Modell kommen aus der Konfiguration), Datenbankschema mit Versionsnummer und Migrationen. Wer eine Messung, eine Regel oder ein Werkzeug ändern will, soll nur eine Stelle anfassen müssen.
6. **Kein Code ohne Doku.** Jedes Modul hat einen Docstring (wofür ist es da?), jede öffentliche Funktion einen Docstring mit Parametern und Rückgabe, und jede Komponente eine kurze Seite unter `docs/`.

---

## 5. Auswertung (Herzstück)

**Aufbau des Labors (Idee, wird in Sprint 0 verfeinert):**

```
[ client ]  ──►  [ router ]  ──►  [ internet ]
 RootPing        netem auf          Ping-Ziel
                 den Interfaces     + DNS-Server (z. B. dnsmasq)
```

- Jedes **Szenario** hat eine erwartete Ursache (Ground Truth), z. B. „Verlust im Heimnetz“, „hohe Latenz beim Provider“, „DNS antwortet nicht“, „DNS langsam“, „alles normal“.
- Pro Szenario laufen RootPing-Messungen ein paar Minuten, dann diagnostizieren **Regel-Baseline** und **Claude-Agent** denselben Vorfall.
- **Kennzahlen:** richtige Schicht (Trefferquote, Konfusionsmatrix), Fehlalarme im Normalbetrieb, Kosten und Dauer pro Diagnose.

**Ehrliche Erwartung:** Bei sauberen Einzelfehlern wird die Regel-Baseline wahrscheinlich genauso gut sein, und das ist ein legitimes Ergebnis. Spannend wird es bei **kombinierten, kurzen oder mehrdeutigen Störungen** (z. B. leichter Verlust plus langsamer DNS, oder Störung nur alle 30 s). Dort soll die Auswertung zeigen, ob die KI echten Mehrwert bringt. Genau diese Ehrlichkeit macht das Projekt in einem Bewerbungsgespräch stark.

---

## 6. Technik

| Bereich | Wahl | Kurz begründet |
|---|---|---|
| Sprache | Python 3.12+, `uv`, `ruff`, `pytest` | Standard, schnelles Setup |
| Messungen | `icmplib`, `dnspython` | Ping ohne Root, präzise DNS-Fehlerarten |
| Speicherung | SQLite (Standardbibliothek) | Keine Installation, eine Datei |
| CLI | `typer` | `rootping run`, `rootping status`, `rootping diagnose` |
| KI | Anthropic Python SDK, Modell konfigurierbar | Tool Use, strukturierte Ausgabe |
| MCP | Offizielles MCP Python SDK | Werkzeuge wiederverwenden |
| Labor | Docker Compose + `tc netem` | Reproduzierbare Störungen |
| Plattform | `platformdirs`, eigenes `platform/`-Modul | Windows und Linux sauber getrennt |
| CI | GitHub Actions (Windows + Linux) | Tests bei jedem PR auf beiden Systemen |

---

## 7. Sprintplan

| Sprint | Ziel | Ergebnis |
|---|---|---|
| 0 | Theorie | Datenmodell, Probe-Schnittstelle, Entscheidungsbaum mit Szenarien, ADRs |
| 1 | Erste Messwerte | Gerüst + CI (Windows + Linux), Ping-Spike auf Windows, drei Messungen, SQLite, `rootping run` |
| 2 | Störungslabor | Docker-Topologie, 5+ Szenarien mit netem, RootPing läuft im Labor, `rootping status` |
| 3 | Erkennen und Regeln | Vorfallerkennung, Regel-Baseline, gemeinsame Werkzeuge |
| 4 | KI-Diagnose | Claude-Agent mit Werkzeugen und Limits, Traceroute auf Anfrage, MCP-Server |
| 5 | Beweisen | Auswertung (Tabelle + Konfusionsmatrix), README mit Demo, Puffer |

**Windows kostet etwa 4–6 Stunden extra**, vor allem in Sprint 1 (zweites CI-System, Gateway-Erkennung, Ping-Spike). Deshalb wandert `rootping status` in Sprint 2, und der Puffer in Sprint 5 wird kleiner.

**Warum das Labor schon in Sprint 2?** Es ist das größte technische Risiko und das Herzstück. Wenn es hakt, merkt man es früh und nicht in der letzten Woche.

---

## 8. Arbeitsweise

Klassischer Rahmen (dieser Plan, Meilensteine, Risiken, ADRs) plus **Kanban mit Wochen-Iterationen**:

- **Board:** GitHub Projects mit Spalten *Backlog · Diese Woche · In Arbeit · Fertig*, WIP-Limit 2
- **Montag (15 Min.):** Wochenziel festlegen, Karten nach „Diese Woche“ ziehen
- **Sonntag (10 Min.):** kurze Retro mit drei Zeilen (gut / nicht gut / ändern) in `docs/journal.md`
- **Entscheidungen:** als ADR in `docs/adr/` (kurz: Kontext, Entscheidung, Konsequenzen)

**Definition of Done**
- Akzeptanzkriterien erfüllt
- Tests für neue Logik, CI grün auf Windows und Linux
- Dokumentiert: Docstrings für Module und öffentliche Funktionen, betroffene Seite unter `docs/` aktualisiert (kein Code ohne Doku)
- Leicht änderbar: keine fest verdrahteten Werte, Konfigurierbares steht in der Konfiguration
- Keine Geheimnisse und keine echten Netzwerkdaten (eigene IPs, SSIDs) im Repo
- Per Pull Request gemergt

---

## 9. Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| Ping ohne Adminrechte klappt auf Windows nicht | Spike gleich in Sprint 1; Plan B System-`ping` oder TCP-Verbindungszeit |
| Systembefehle liefern je nach Sprache andere Ausgaben (deutsches vs. englisches Windows) | Wo möglich Bibliotheken oder strukturierte Ausgaben (PowerShell-Objekte) statt Text parsen |
| Traceroute wird falsch gedeutet (Router antworten absichtlich langsam) | Verlust an Zwischen-Hops zählt nur, wenn er bis zum Ziel anhält; Regel steht im Agent-Prompt |
| Traceroute-Ausgabe unterscheidet sich je System und Sprache | Nur IPs und Zeiten lesen (`-d`/`-n`), Tests mit deutschen und englischen Beispielausgaben |
| Labor mit netem funktioniert nicht wie gedacht (Rechte, Docker-Netzwerke) | Früh in Sprint 2; Container mit `NET_ADMIN`; notfalls nur ein Container mit netem auf dem eigenen Interface |
| Messungen laufen nur gegen das echte Netz | Ziele immer aus der Konfiguration, nie fest im Code (Probe-Schnittstelle) |
| Fehlalarme durch Laptop-Ruhezustand | Zeitsprünge erkennen, als „Messlücke“ markieren statt als Störung |
| Fehlalarme durch Netz- oder VPN-Wechsel | Netzwerk-Kontext pro Messung speichern; Wechsel ist ein eigenes Ereignis |
| Normalwerte nach Tageszeit brauchen Wochen an Daten | In v1 feste Schwellwerte + kurzer gleitender Median |
| API-Kosten | KI nur bei Vorfällen, Höchstzahl pro Tag, Ausgabenlimit in der Anthropic Console, Kosten pro Diagnose loggen |
| Datenschutz | Nur zusammengefasste Werte an die API, private IPs durch Platzhalter ersetzt |
| Umfang wächst | Liste „Nicht in v1“ (Abschnitt 2) ist verbindlich; neue Ideen in den Backlog |

---

## 10. Sprint 0: was noch zu klären ist

Diese Themen gehen wir einzeln durch. Jedes endet als Markdown-Datei unter `docs/`:

1. **Datenmodell** für Messungen, Vorfälle und Diagnosen → [datenmodell.md](datenmodell.md) ✓
2. **Probe-Schnittstelle** (wie sieht ein Messungs-Plugin aus?) → [probes.md](probes.md) ✓
3. **Entscheidungsbaum + Testszenarien** (Regel-Baseline und Ground Truth fürs Labor) → [diagnose.md](diagnose.md) ✓
4. **Erste ADRs:** z. B. SQLite statt Zeitreihen-DB, `icmplib` statt System-`ping`, Windows + Linux mit Labor nur unter Linux, Regeln vor KI → `docs/adr/`
