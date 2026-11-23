import datetime as dt
import logging

from utils import (
    AGGREGATED_RESULT_FILE,
    AGGREGATED_RESULT_KIND,
    DAILY_RESULT_FILE,
    DAILY_RESULT_KIND,
    RESULTS_PREFIX,
    S3_PROFILE,
    Context,
    results_key,
    run_aws_s3,
    s3_uri,
)
from models import MAX_WINDOW_DAYS
from models.paths import WorkingFiles

log = logging.getLogger(__name__)


def download_daily_results(ctx: Context) -> None:
    """Lädt per aws s3 sync die Tagesdateien der letzten MAX_WINDOW_DAYS Tage (längstes festes Fenster) bis as_of
    und das Aggregat des Vortags nach aggregate/s3_results/ (Layout wie unter results/ im Bucket).

    Fehlende Tage sind erlaubt und landen später in coverage.days_missing.
    """
    results_dir = ctx.workingPathOf(WorkingFiles.AGGREGATE_S3_RESULTS_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)
    log.debug("results_dir: %s", results_dir)
    if not ctx.force_reload and any(results_dir.iterdir()):
        log.info("aggregate/s3_results/ existiert bereits und --force-reload nicht gesetzt, überspringe Download")
        return

    as_of = ctx.date_of_data
    days = [as_of - dt.timedelta(days=i) for i in range(MAX_WINDOW_DAYS)]
    previous_day = as_of - dt.timedelta(days=1)
    log.info("Lade Tagesdateien %s bis %s und Aggregat vom %s aus %s (Profil: %s)",
             days[-1], as_of, previous_day, s3_uri(RESULTS_PREFIX), S3_PROFILE or "aus Umgebung")

    includes = [
        *(results_key(d, DAILY_RESULT_KIND, DAILY_RESULT_FILE) for d in days),
        results_key(previous_day, AGGREGATED_RESULT_KIND, AGGREGATED_RESULT_FILE),
    ]
    run_aws_s3(
        "sync", f"{s3_uri(RESULTS_PREFIX)}/", str(results_dir),
        "--exclude", "*",
        *(arg for pattern in includes for arg in ("--include", pattern)),
    )

    daily = sum(1 for d in days if (results_dir / results_key(d, DAILY_RESULT_KIND, DAILY_RESULT_FILE)).is_file())
    has_previous = (results_dir / results_key(previous_day, AGGREGATED_RESULT_KIND, AGGREGATED_RESULT_FILE)).is_file()
    log.info("In %s: %d von %d Tagesdateien, Vortags-Aggregat %s",
             results_dir, daily, len(days), "vorhanden" if has_previous else "fehlt")

    if daily == 0 and not has_previous:
        log.error("Weder Tagesdateien noch Vortags-Aggregat für %s gefunden", as_of.isoformat())
        raise SystemExit(f"Keine Tagesdateien und kein Vortags-Aggregat für {as_of.isoformat()} in {results_dir}")
