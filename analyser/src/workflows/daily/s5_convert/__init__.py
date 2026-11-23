"""Ergebnisse des Tages nach dem Schema zu einem DailyResult zusammensetzen (Schritt 13)."""

import logging
from pathlib import Path

from utils import Context
from .t1_convert_to_json import convert_to_json

log = logging.getLogger(__name__)


def run(ctx: Context) -> None:
    log.info(" ---- Schritt 5: Ergebnisse des Tages nach dem Schema zu einem DailyResult zusammensetzen")
    convert_to_json(ctx)
    log.info(" ---- Schritt 5 abgeschlossen.")