"""Logging für RootPing: kurz in die Konsole (stderr), ausführlich in eine Datei.

Eine Datei pro Prozess (``run.log``), weil Windows eine Log-Datei nicht
umbenennen kann, solange ein anderer Prozess sie offen hat
(``docs/tech-stack.md`` Abschnitt 3.15). Logs gehen nie nach stdout: Das
bleibt später dem MCP-Protokoll vorbehalten.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import platformdirs

from rootping.config import APP_NAME

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
MAX_LOG_BYTES = 2_000_000
BACKUP_COUNT = 3


def default_log_dir() -> Path:
    """Gibt den Log-Ordner des Betriebssystems zurück (über ``platformdirs``)."""
    return Path(platformdirs.user_log_dir(APP_NAME, appauthor=False))


def setup_logging(process: str, *, verbose: bool = False, log_dir: Path | None = None) -> Path:
    """Richtet das Logging für einen Prozess ein.

    Args:
        process: Kurzname des Prozesses; ergibt den Dateinamen ``<process>.log``.
        verbose: Auch Detailmeldungen (DEBUG) in der Konsole zeigen.
        log_dir: Ordner für die Log-Datei; Standard ist :func:`default_log_dir`.

    Returns:
        Pfad der Log-Datei.
    """
    folder = log_dir or default_log_dir()
    folder.mkdir(parents=True, exist_ok=True)
    log_file = folder / f"{process}.log"

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    file_handler = RotatingFileHandler(
        log_file, maxBytes=MAX_LOG_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)  # fremde Bibliotheken: nur Wichtiges
    root.addHandler(console)
    root.addHandler(file_handler)
    logging.getLogger(APP_NAME).setLevel(logging.DEBUG)  # RootPing selbst: alles in die Datei
    return log_file
