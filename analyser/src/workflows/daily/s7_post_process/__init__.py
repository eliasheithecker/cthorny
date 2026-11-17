"""Post-Process: Arbeitsverzeichnis aufräumen."""

import logging

from utils import Context

from .t1_cleanup import cleanup

log = logging.getLogger(__name__)


def run(ctx: Context) -> None:
    log.info(" ---- Schritt 7: Post-Process, Aufräumen")
    cleanup(ctx)
    log.info(" ---- Schritt 7 abgeschlossen.")
