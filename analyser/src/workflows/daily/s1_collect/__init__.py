"""Inputs für den UTC-Tag beschaffen und im Arbeitsverzeichnis ablegen."""

import logging

from utils import Context

from .t1_download_raw import download_raw

log = logging.getLogger(__name__)


def run(ctx: Context) -> None:
    log.info(" ---- Schritt 1: Rohdaten einsammeln und im Arbeitsverzeichnis ablegen")
    download_raw(ctx)
    log.info(" ---- Schritt 1 abgeschlossen.")
