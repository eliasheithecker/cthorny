import logging

from utils import Context

log = logging.getLogger(__name__)

def aggregate_workflow(ctx: Context) -> None:
    log.info(" ---- Starte aggregierte Auswertung für Stichtag %s", ctx.date_of_data)
    log.warning("Aggregate workflow ist noch nicht implementiert.")
    log.info(" ---- Aggregierte Auswertung für Stichtag %s abgeschlossen", ctx.date_of_data)
    