import logging

from utils import Context, S3_BUCKET, S3_PROFILE, date_partition, run_aws_s3
from models.paths import WorkingFiles

log = logging.getLogger(__name__)

# Zum Testen auf kleineren Daten: Muster für region=..., z. B. "fra1"; "*" = alle Regionen
REGION_FILTER = "fra1"


def download_raw(ctx: Context) -> None:
    """Lädt die Rohdaten des UTC-Tages per aws s3 sync nach raw/.

    Geladen werden alle Deskriptoren, alle Thorny-Logs und nur die PCAPs des Tages
    (year=/month=/day=). ssh/, tls/ und zeek/ werden nicht geladen.
    Das lokale Layout spiegelt den Bucket. sync überspringt bereits vorhandene,
    unveränderte Dateien, ein bestehendes raw/ wird also weiterverwendet.
    """
    raw_dir = ctx.workingPathOf(WorkingFiles.RAW_DIR)
    raw_dir.mkdir(parents=True, exist_ok=True)
    log.debug("raw_dir: %s", raw_dir)
    if not ctx.force_reload and any(raw_dir.iterdir()):
        log.info("raw/ existiert bereits und --force-reload nicht gesetzt, überspringe Download")
        return


    d = ctx.date_of_data
    log.info("Lade Rohdaten für %s aus %s (Profil: %s, Region: %s)",
             d.isoformat(), S3_BUCKET, S3_PROFILE or "aus Umgebung", REGION_FILTER)

    # Deskriptoren haben keine Region im Pfad und werden immer vollständig geladen
    includes = [
        "descriptors/*",
        f"provider=*/region={REGION_FILTER}/ip=*/thorny/log-*.jsonl",
        f"provider=*/region={REGION_FILTER}/ip=*/{date_partition(d)}/*",
    ]
    run_aws_s3(
        "sync", S3_BUCKET, str(raw_dir),
        "--exclude", "*",
        *(arg for pattern in includes for arg in ("--include", pattern)),
    )

    descriptors = sum(1 for p in ctx.workingPathOf(WorkingFiles.RAW_DESCRIPTORS_DIR).rglob("*") if p.is_file())
    handler_logs = sum(1 for p in raw_dir.rglob("log-*.jsonl") if p.parent.name == "thorny" and p.is_file())
    day_part = f"{date_partition(d)}/"
    pcaps = sum(1 for p in raw_dir.rglob("*.pcap.gz") if day_part in p.as_posix() and p.is_file())
    log.info("Rohdaten in %s: %d Deskriptoren, %d Handler-Logs, %d PCAPs des Tages",
             raw_dir, descriptors, handler_logs, pcaps)

    if pcaps == 0:
        log.error("Keine PCAPs für %s gefunden", d.isoformat())
        raise SystemExit(f"Keine PCAPs für {d.isoformat()} in {raw_dir}")
