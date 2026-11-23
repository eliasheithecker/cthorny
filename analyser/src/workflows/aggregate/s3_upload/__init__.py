"""Aggregierte Ergebnisdatei in den S3 schreiben."""

import logging

from utils import Context

from .t1_upload import upload_aggregated_result

log = logging.getLogger(__name__)


def run(ctx: Context) -> None:
    log.info(" ---- Schritt 3: Aggregierte Ergebnisdatei in den S3 schreiben")
    upload_aggregated_result(ctx)
    log.info(" ---- Schritt 3 abgeschlossen.")
