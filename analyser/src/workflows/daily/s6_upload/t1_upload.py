import logging

from utils import Context, S3_PROFILE, date_partition, s3_uri, run_aws_s3
from models import WorkingFiles

log = logging.getLogger(__name__)


def upload_daily_result(ctx: Context) -> None:
    """Lädt die daily_result.json nach s3://<bucket>/results/year=<YYYY>/month=<MM>/day=<DD>/daily/daily_result.json hoch.

    Eine bereits vorhandene Datei im Bucket wird überschrieben.
    """
    daily_result_file = ctx.workingPathOf(WorkingFiles.DAILY_RESULT_JSON)
    if not daily_result_file.exists():
        log.warning("DailyResult JSON file does not exist: %s", daily_result_file)
        raise FileNotFoundError(f"DailyResult JSON file does not exist: {daily_result_file}")

    target = s3_uri("results", date_partition(ctx.date_of_data), "daily", "daily_result.json")
    log.info("Lade %s nach %s hoch (Profil: %s)",
             daily_result_file, target, S3_PROFILE or "aus Umgebung")
    run_aws_s3("cp", str(daily_result_file), target)
    log.info("DailyResult hochgeladen: %s", target)
