import logging

from models import WorkingFiles
from utils import AGGREGATED_RESULT_FILE, AGGREGATED_RESULT_KIND, S3_PROFILE, Context, results_uri, run_aws_s3

log = logging.getLogger(__name__)


def upload_aggregated_result(ctx: Context) -> None:
    """Lädt die aggregated.json nach s3://<bucket>/results/year=<YYYY>/month=<MM>/day=<DD>/aggregated/aggregated.json hoch.

    Eine bereits vorhandene Datei im Bucket wird überschrieben.
    """
    result_file = ctx.workingPathOf(WorkingFiles.AGGREGATED_RESULT_JSON)
    if not result_file.exists():
        log.warning("AggregatedResult JSON file does not exist: %s", result_file)
        raise FileNotFoundError(f"AggregatedResult JSON file does not exist: {result_file}")

    target = results_uri(ctx.date_of_data, AGGREGATED_RESULT_KIND, AGGREGATED_RESULT_FILE)
    log.info("Lade %s nach %s hoch (Profil: %s)", result_file, target, S3_PROFILE or "aus Umgebung")
    run_aws_s3("cp", str(result_file), target)
    log.info("AggregatedResult hochgeladen: %s", target)
