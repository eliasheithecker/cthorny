"""Tagesdateien und Vortags-Aggregat aus dem S3 ins Arbeitsverzeichnis laden."""

import logging

from utils import Context

from .t1_download_daily_results import download_daily_results

log = logging.getLogger(__name__)


def run(ctx: Context) -> None:
    log.info(" ---- Schritt 1: Tagesdateien für die Fenster laden")
    download_daily_results(ctx)
    log.info(" ---- Schritt 1 abgeschlossen.")
