"""Indikatoren je Scanner und Tag berechnen."""

import logging
from pathlib import Path

from utils import Context

from .t1_event_levels import event_levels
from .t2_group_sanners import group_scanners
from .t3_analyse_traffic import analyse_traffic
from .t4_sensor_metadata import sensor_metadata

log = logging.getLogger(__name__)


def run(ctx: Context) -> None:
    log.info(" ---- Schritt 4: Indikatoren je Scanner und Tag berechnen")
    event_levels(ctx)
    group_scanners(ctx)
    analyse_traffic(ctx)
    sensor_metadata(ctx)
    log.info(" ---- Schritt 4 abgeschlossen.")
