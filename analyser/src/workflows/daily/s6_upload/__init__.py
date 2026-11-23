"""Ergebnisdateien in den S3 schreiben."""

import logging

from utils import Context

from .t1_upload import upload_daily_result

log = logging.getLogger(__name__)


def run(ctx: Context) -> None:
    log.info(" ---- Schritt 6: Ergebnisdateien in den S3 schreiben")
    upload_daily_result(ctx)
    log.info(" ---- Schritt 6 abgeschlossen.")
