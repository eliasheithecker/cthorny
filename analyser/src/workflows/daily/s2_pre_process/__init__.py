"""Rohdaten des Tages bereinigen und in auswertbare Tabellen überführen."""

import logging

from utils import Context

from .t1_merge_handler_logs import merge_handler_logs
from .t2_merge_pcaps import merge_pcaps
from .t3_extract_sensors import extract_sensors
from .t4_flatten_handler_logs import flatten_handler_logs
from .t5_filter_pcap import filter_pacap

log = logging.getLogger(__name__)

def run(ctx: Context) -> None:
    log.info(" ---- Schritt 2: Rohdaten bereinigen und in auswertbare Tabellen überführen")
    merge_handler_logs(ctx)
    merge_pcaps(ctx)
    extract_sensors(ctx)
    flatten_handler_logs(ctx)
    filter_pacap(ctx)
    log.info(" ---- Schritt 2 abgeschlossen.")
