"""Verarbeitungsschritte des nächtlichen Laufs, siehe idee.md "Verarbeitungsschritte".

Reihenfolge: s1_collect -> s2_pre_process -> s3_identify -> s4_analyse -> s5_post_process -> s6_aggregate -> s7_publish
"""

import logging

from .s1_collect import run as s1_collect
from .s2_pre_process import run as s2_pre_process
from .s3_identify import run as s3_identify
from .s4_analyse import run as s4_analyse
from .s5_convert import run as s5_convert
from .s6_upload import run as s6_upload
from .s7_post_process import run as s7_post_process

from utils import Context

log = logging.getLogger(__name__)


def daily_workflow(ctx: Context) -> None:
    log.info(" ---- Starte tägliche Auswertung für %s", ctx.date_of_data)
    s1_collect(ctx)
    s2_pre_process(ctx)
    s3_identify(ctx)
    s4_analyse(ctx)
    s5_convert(ctx)
    s6_upload(ctx)
    s7_post_process(ctx)
    log.info(" ---- Tägliche Auswertung für %s abgeschlossen", ctx.date_of_data)