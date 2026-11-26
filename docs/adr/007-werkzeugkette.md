# ADR-007: Werkzeugkette (Python, uv, ruff, Pyright, prek)

- **Status:** vorgeschlagen
- **Datum:** 2026-11-26

## Kontext
Der Plan nannte „Python 3.12+, uv, ruff, pytest“. Seitdem ist Python 3.15 erschienen, 3.12 bekommt nur noch Sicherheitsupdates, und Kais Grundregeln („leicht änderbar, kein Code ohne Doku“) sollen möglichst automatisch geprüft werden. Details und Quellen: [tech-stack.md](../tech-stack.md), Abschnitte 3.1–3.6.

## Entscheidung
- **Python:** `requires-python = ">=3.14"`, entwickelt auf 3.15, CI testet 3.14 und 3.15.
- **uv** für Python-Installation, Umgebung, Abhängigkeiten und Build; `uv.lock` im Repo; `exclude-newer = "7 days"` als Cooldown; src-Layout mit `uv_build`.
- **ruff** für Lint und Format, inklusive Docstring-Regeln (`D`, Google-Stil), damit „kein Code ohne Doku“ in CI geprüft wird, sowie `ASYNC`, `DTZ`, `T201`, `PLW1514`, `RUF006`, `S603`.
- **Pyright** (`standard`) als verbindliche Typprüfung; ty wird beobachtet.
- **prek** für Git-Hooks mit Standard-`.pre-commit-config.yaml`.
- **pytest 9, pytest-asyncio 1.x, Hypothesis** für Tests.

## Betrachtete Alternativen
- **Python 3.12 beibehalten:** nur noch Sicherheitsupdates.
- **Nur Python 3.15:** einfacher, aber ohne getestete Rückfallebene für eine 7 Wochen alte Version.
- **Poetry/PDM/Hatch:** funktionieren, uv deckt alles ab und ist der heutige Standard.
- **mypy:** geringere Konformität mit der Typing-Spezifikation, langsamer. **ty:** noch Beta (0.0.x).
- **pre-commit:** gleichwertig; prek nutzt dieselbe Konfiguration, ein Wechsel kostet nichts.

## Konsequenzen
- Docstrings, UTC-Zeitstempel, explizite Kodierungen und das `print`-Verbot (wichtig für den MCP-Server) werden automatisch geprüft.
- Untergrenzen von Abhängigkeiten müssen zum Cooldown passen (`uv add` setzt sonst die neueste Version als Untergrenze).
- Wenn ty 1.0 erscheint, wird der Wechsel neu bewertet (neues ADR).
