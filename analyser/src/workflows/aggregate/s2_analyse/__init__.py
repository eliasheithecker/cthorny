"""Tagesdateien zu den Zeitfenstern zusammenführen und als AggregatedResult speichern."""

import logging

from utils import Context

from .t2_write_aggregated_result import write_aggregated_result

log = logging.getLogger(__name__)


def run(ctx: Context) -> None:
    log.info(" ---- Schritt 2: Zeitfenster aggregieren")
    write_aggregated_result(ctx)
    log.info(" ---- Schritt 2 abgeschlossen.")
