# ADR-008: Claude-Agent über die Messages API mit eigener Schleife

- **Status:** vorgeschlagen
- **Datum:** 2026-11-26

## Kontext
Der Agent soll bei einer Störung mit Werkzeugen (Messwerte lesen, `ping_now`, `dns_lookup_now`, Traceroute) die Ursache eingrenzen und eine strukturierte Diagnose liefern, die automatisch mit der Regel-Baseline verglichen wird. Die Werkzeuge müssen lokal laufen (Router anpingen, lokale SQLite lesen). Es gibt vier Wege, einen Claude-Agenten zu bauen: eigene Schleife, Tool Runner (SDK-Helfer, Beta), Claude Agent SDK, Claude Managed Agents. Details: [tech-stack.md](../tech-stack.md), Abschnitt 3.20.

## Entscheidung
- **`anthropic` 2.x**, **Messages API**, **eigene Schleife** (`while stop_reason == "tool_use"`), etwa 40 Zeilen.
- Werkzeuge kommen aus `tools.py` (dieselben Funktionen nutzt der MCP-Server).
- Endergebnis über **strukturierte Ausgabe** (`output_config.format` mit JSON-Schema aus dem Pydantic-Modell `Diagnosis`), nicht über erzwungenen Werkzeugaufruf (auf Claude Opus 5.5 nicht erlaubt).
- Modell, Effort, Höchstzahl der Werkzeugaufrufe und Tageslimit aus der Konfiguration. Startwert: `claude-opus-5-5`, das laut Modellübersicht von Anthropic empfohlene Einstiegsmodell (abgerufen 26.11.2026, siehe tech-stack.md Q45).
- Tokens, Kosten, Modell-ID und SDK-Version werden pro Diagnose gespeichert. Prompt-Caching für System-Prompt und Werkzeugliste.

## Betrachtete Alternativen
- **Tool Runner** (`client.beta.messages.tool_runner`): spart Code, ist aber Beta, und die Schleife ist genau der Teil, der kontrolliert und gezeigt werden soll.
- **Claude Agent SDK:** bringt Claude Code mit eingebauten Datei- und Shell-Werkzeugen mit (Windows-Wheel 178 MB). RootPing braucht diese Werkzeuge gerade nicht.
- **Claude Managed Agents:** Anthropic betreibt Schleife und Sandbox; lokale Werkzeuge müssten trotzdem auf dem eigenen Rechner laufen. Beta, zusätzliche Laufzeitkosten, Verlauf wird bei Anthropic gespeichert. Sinnvoll erst, wenn RootPing als gehosteter Dienst laufen soll.
- **Frameworks (LangChain, PydanticAI):** zusätzliche Abstraktion ohne Nutzen bei nur einem Anbieter.

## Konsequenzen
- Volle Kontrolle über Limits, Kostenprotokoll und Abbruchgründe; keine Beta-Abhängigkeit im Kern.
- Seit API-Version 2026-10-21 gibt es kein `temperature` mehr. Antworten sind nicht deterministisch; die Auswertung macht mehrere Läufe pro Szenario und gibt die Streuung an.
- Ein späterer Wechsel auf den Tool Runner oder Managed Agents betrifft nur `diagnose/agent.py`.
