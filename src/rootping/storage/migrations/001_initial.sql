-- Migration 001: Grundtabellen für Sprint 1 (Messungen, Netzwerk-Kontexte, Ereignisse).
-- Beschreibung aller Spalten: docs/datenmodell.md
-- STRICT: SQLite prüft die Spaltentypen und lehnt z. B. Text in einer REAL-Spalte ab.

-- In welchem Netz gemessen wurde. Ein bekanntes Netz (gleicher Router, gleiche
-- Netzwerkkarte, gleiches VPN) bekommt beim Wiederkehren dieselbe Zeile.
CREATE TABLE network_contexts (
    id         INTEGER PRIMARY KEY,
    gateway    TEXT NOT NULL,                             -- Heimrouter, auch bei aktivem VPN
    interface  TEXT NOT NULL,                             -- Netzwerkkarte zum Heimrouter
    vpn        TEXT NOT NULL DEFAULT '',                  -- VPN-Adapter oder leer
    first_seen TEXT NOT NULL,
    UNIQUE (gateway, interface, vpn)
) STRICT;

-- Eine Zeile pro Messrunde und Ziel (Zusammenfassung, nicht jedes Paket).
CREATE TABLE measurements (
    id         INTEGER PRIMARY KEY,
    ts         TEXT    NOT NULL,                          -- Beginn der Runde, ISO 8601 UTC
    probe      TEXT    NOT NULL,                          -- z. B. ping_gateway
    target     TEXT    NOT NULL,                          -- z. B. 1.1.1.1
    ok         INTEGER NOT NULL CHECK (ok IN (0, 1)),
    latency_ms REAL,
    loss_pct   REAL CHECK (loss_pct BETWEEN 0 AND 100),
    jitter_ms  REAL,
    max_ms     REAL,
    error      TEXT,                                      -- fester Fehlercode, z. B. no_reply
    context_id INTEGER REFERENCES network_contexts (id)   -- leer = kein Netz erkannt
) STRICT;

-- Fast jede Abfrage lautet: "Werte von Messung X im Zeitraum Y".
CREATE INDEX idx_measurements_probe_ts ON measurements (probe, ts);

-- Besondere Ereignisse: Messlücke (gap) oder Netzwechsel (network_change).
-- Erlaubte Typen prüft der Python-Code (EventType), damit neue Typen keine
-- Schemaänderung brauchen.
CREATE TABLE events (
    id         INTEGER PRIMARY KEY,
    ts         TEXT NOT NULL,
    type       TEXT NOT NULL,
    context_id INTEGER REFERENCES network_contexts (id),
    details    TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(details))
) STRICT;
