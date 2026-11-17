import logging
import subprocess
from datetime import date

log = logging.getLogger(__name__)

S3_BUCKET = "s3://msc-juri/"
# Zum Testen: AWS-Profil für den Bucket; None = Profil aus der Umgebung (AWS_PROFILE / IAM-Rolle)
S3_PROFILE: str | None = "uni"


def date_partition(d: date) -> str:
    """Datumsteil der Bucket-Pfade, z. B. year=2026/month=11/day=16 (ohne Slash am Ende)."""
    return f"year={d.year}/month={d.month:02d}/day={d.day:02d}"


def s3_uri(*parts: str) -> str:
    """S3-URI im Bucket, z. B. s3_uri("results", "2026-11-16") -> s3://msc-juri/results/2026-11-16"""
    return S3_BUCKET + "/".join(p.strip("/") for p in parts)


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
