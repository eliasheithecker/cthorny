import datetime as dt
import logging

from models import MAX_WINDOW_DAYS, SCHEMA_VERSION, AggregatedResult
from models.paths import WorkingFiles
from utils import (
    AGGREGATED_RESULT_FILE,
    AGGREGATED_RESULT_KIND,
    DAILY_RESULT_FILE,
    DAILY_RESULT_KIND,
    Context,
    read_json,
    results_key,
    write_json,
)

from .t1_aggregate_windows import aggregate_windows

log = logging.getLogger(__name__)


def write_aggregated_result(ctx: Context) -> None:
    """Berechnet aus den geladenen Tagesdateien (und dem Vortags-Aggregat) das AggregatedResult und speichert es als JSON."""
    output_file = ctx.workingPathOf(WorkingFiles.AGGREGATED_RESULT_JSON)
    if not ctx.force_reload and output_file.exists():
        log.info("Aggregated result already exists, skipping step")
        return

    results_dir = ctx.workingPathOf(WorkingFiles.AGGREGATE_S3_RESULTS_DIR)
    as_of = ctx.date_of_data

    daily_files = {}
    for i in range(MAX_WINDOW_DAYS):
        day = as_of - dt.timedelta(days=i)
        path = results_dir / results_key(day, DAILY_RESULT_KIND, DAILY_RESULT_FILE)
        if path.is_file():
            daily_files[day] = path

    previous = None
    previous_file = results_dir / results_key(as_of - dt.timedelta(days=1), AGGREGATED_RESULT_KIND, AGGREGATED_RESULT_FILE)
    if previous_file.is_file():
        previous = read_json(previous_file)
        if previous.get("schema_version") != SCHEMA_VERSION:
            log.warning("Vortags-Aggregat hat schema_version %s statt %s, wird ignoriert",
                        previous.get("schema_version"), SCHEMA_VERSION)
            previous = None

    result = AggregatedResult(
        schema_version=SCHEMA_VERSION,
        as_of=as_of,
        generated_at=dt.datetime.now(dt.UTC),
        windows=aggregate_windows(as_of, daily_files, previous),
    )
    write_json(result, output_file)
    log.info("Aggregated result saved to %s", output_file)
