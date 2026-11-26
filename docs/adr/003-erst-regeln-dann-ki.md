# ADR-003: Erst Regeln, dann KI

- **Status:** angenommen
- **Datum:** 2026-11-26

## Kontext
RootPing soll Störungen erkennen und erklären. Man könnte jede Messung direkt von Claude bewerten lassen. Das wäre teuer, langsam, nicht reproduzierbar und schwer zu testen. Außerdem soll gezeigt werden, wie gut die KI wirklich ist.

## Entscheidung
1. **Erkennen ohne KI:** Feste, konfigurierbare Schwellen markieren Auffälligkeiten; eine Störung entsteht erst, wenn sie anhalten oder sich häufen (siehe `docs/diagnose.md`).
2. **Erklären mit Regeln und KI:** Bei jeder Störung diagnostizieren **beide**, die Regel-Baseline (Entscheidungsbaum) und der Claude-Agent. Beide Ergebnisse werden in derselben Tabelle gespeichert.
3. **Messen:** Im Labor wird verglichen, wer die richtige Ursache findet.

## Betrachtete Alternativen
- **Nur KI:** beeindruckend in der Demo, aber teuer und ohne Beleg, dass es funktioniert.
- **Nur Regeln:** zuverlässig, aber kein KI-Projekt und schwach bei kombinierten oder kurzen Störungen.

## Konsequenzen
- KI-Kosten nur bei echten Störungen, zusätzlich Tageslimit.
- Erkennung und Regeln sind ohne API-Schlüssel vollständig testbar.
- Die Regel-Baseline ist bewusst einfach („unterste Schicht gewinnt“). Ihre Schwächen sind Teil des Experiments, nicht ein Fehler.
