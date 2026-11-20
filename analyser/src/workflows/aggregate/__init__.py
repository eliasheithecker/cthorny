"""Aggregierte Auswertung: Tagesdateien zu den Zeitfenstern last_7d, last_31d, last_365d und all zusammenführen.

Reihenfolge: s1_pre_process -> s2_analyse -> s3_upload -> s4_post_process
"""

import logging

from utils import Context

from .s1_pre_process import run as s1_pre_process
from .s2_analyse import run as s2_analyse
from .s3_upload import run as s3_upload
from .s4_post_process import run as s4_post_process

log = logging.getLogger(__name__)


def aggregate_workflow(ctx: Context) -> None:
    log.info(" ---- Starte aggregierte Auswertung für Stichtag %s", ctx.date_of_data)
    s1_pre_process(ctx)
    s2_analyse(ctx)
    s3_upload(ctx)
    s4_post_process(ctx)
    log.info(" ---- Aggregierte Auswertung für Stichtag %s abgeschlossen", ctx.date_of_data)
