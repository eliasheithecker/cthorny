import logging
import subprocess
from datetime import date

log = logging.getLogger(__name__)

S3_BUCKET = "s3://msc-juri/"
# Zum Testen: AWS-Profil für den Bucket; None = Profil aus der Umgebung (AWS_PROFILE / IAM-Rolle)
S3_PROFILE: str | None = "uni"
# Ordner im Bucket für die Ergebnisse (daily und aggregated)
RESULTS_PREFIX = "results"
DAILY_RESULT_KIND, DAILY_RESULT_FILE = "daily", "daily_result.json"
AGGREGATED_RESULT_KIND, AGGREGATED_RESULT_FILE = "aggregated", "aggregated.json"


def date_partition(d: date) -> str:
    """Datumsteil der Bucket-Pfade, z. B. year=2026/month=11/day=16 (ohne Slash am Ende)."""
    return f"year={d.year}/month={d.month:02d}/day={d.day:02d}"


def s3_uri(*parts: str) -> str:
    """S3-URI im Bucket, z. B. s3_uri("results", "2026-11-16") -> s3://msc-juri/results/2026-11-16"""
    return S3_BUCKET + "/".join(p.strip("/") for p in parts)


def results_key(d: date, kind: str, filename: str) -> str:
    """Pfad unterhalb von results/, z. B. year=2026/month=11/day=16/daily/daily_result.json"""
    return f"{date_partition(d)}/{kind}/{filename}"


def results_uri(d: date, kind: str, filename: str) -> str:
    """Ablage der Ergebnisse, z. B. s3://msc-juri/results/year=2026/month=11/day=16/daily/daily_result.json"""
    return s3_uri(RESULTS_PREFIX, results_key(d, kind, filename))


def run_aws_s3(subcommand: str, *args: str) -> None:
    """Führt `aws s3 <subcommand> <args>` mit Profil und passender Ausgabe aus."""
    command = ["aws", "s3", subcommand, *args]
    # Bei DEBUG gibt aws den Fortschritt und jede übertragene Datei direkt im Terminal aus, sonst nur Fehler
    if not log.isEnabledFor(logging.DEBUG):
        command += ["--no-progress", "--only-show-errors"]
    if S3_PROFILE:
        command += ["--profile", S3_PROFILE]
    log.debug("aws command: %s", command)
    subprocess.run(command, check=True)
