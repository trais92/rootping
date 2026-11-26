# ADR-001: SQLite als Speicher

- **Status:** angenommen
- **Datum:** 2026-11-26

## Kontext
RootPing speichert etwa 40.000 Messrunden pro Tag, dazu Vorfälle, Diagnosen und Traceroutes. Es läuft lokal auf einem einzelnen PC (Windows oder Linux), soll ohne Installation weiterer Software funktionieren und leicht verständlich sein.

## Entscheidung
Alle Daten liegen in **einer SQLite-Datei**. Zugriff nur über das Modul `storage`, Schema-Änderungen über nummerierte Migrationen (`PRAGMA user_version`).

## Betrachtete Alternativen
- **Zeitreihen-Datenbank (InfluxDB, TimescaleDB):** ideal für Messwerte, aber ein zusätzlicher Dienst, der installiert und betrieben werden muss. Für ein Gerät überdimensioniert.
- **CSV- oder JSON-Dateien:** einfach, aber Abfragen über Zeiträume und Verknüpfungen (Vorfall ↔ Diagnose ↔ Labor-Durchlauf) wären mühsam.

## Konsequenzen
- Keine Installation, in Python eingebaut, läuft auf Windows und Linux gleich.
- Der Vergleich KI vs. Regeln ist eine einzige SQL-Abfrage.
- Nur ein Schreiber gleichzeitig: passt, weil nur `storage` schreibt.
- Ein späterer Wechsel (z. B. PostgreSQL) betrifft nur das Modul `storage`.
