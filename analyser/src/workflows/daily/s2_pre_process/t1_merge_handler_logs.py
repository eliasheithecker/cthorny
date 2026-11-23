import logging
import shutil
from collections import defaultdict
from pathlib import Path

from utils import Context
from models.paths import WorkingFiles

log = logging.getLogger(__name__)

COPY_BUFFER = 1024 * 1024  # 1 MiB je Lese-/Schreibvorgang
PARSE_LOGS_FILE = ""

def merge_handler_logs(ctx: Context) -> None:
    """Führt die Handler-Logs aus raw/ je Sensor zu einer Datei zusammen.

    Sucht alle raw/**/thorny/log-*.jsonl, liest die Sensor-IP aus dem Pfadteil ip=...
    und hängt die Logs in sortierter Reihenfolge an interim/handlers/<ip>.jsonl an
    (Punkte der IP als Bindestriche). Bestehende Zieldateien werden nicht geleert.
    Ersetzt das bisherige Bash-Skript (find | sort | awk | cat >>).
    """
    output_dir = ctx.workingPathOf(WorkingFiles.HANDLERS_DIR)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    log.debug("output_dir: %s", output_dir)
    
    if not ctx.force_reload and any(output_dir.iterdir()):
        log.info("Handler-Logs bereits zusammengeführt, überspringe Schritt")
        return
    
    raw_dir = ctx.workingPathOf(WorkingFiles.RAW_DIR)
    log.debug("raw_dir: %s", raw_dir)

    # find raw -type f -path '*/thorny/log-*.jsonl' | sort
    files = sorted(
        (p for p in raw_dir.rglob("log-*.jsonl") if p.parent.name == "thorny" and p.is_file()),
        key=str,
    )
    if len(files) == 0:
        log.error("Keine Handler-Logs gefunden")
        raise SystemExit(f"eine Handler-Logs gefunden in {raw_dir}")
    log.debug("%d Handler-Logs gefunden", len(files))

    # awk: Sensor-IP aus dem Pfadteil ip=... ziehen, Punkte durch Bindestriche ersetzen
    by_ip: dict[str, list[Path]] = defaultdict(list)
    for file in files:
        for part in file.relative_to(raw_dir).parts:
            if part.startswith("ip="):
                by_ip[part[3:].replace(".", "-")].append(file)

    # cat "$file" >> "$OUTDIR/${ip}.jsonl": Zieldatei je IP nur einmal öffnen
    for ip, ip_files in by_ip.items():
        target = output_dir / f"{ip}.jsonl"
        with open(target, "ab") as out:
            for file in ip_files:
                with open(file, "rb") as src:
                    shutil.copyfileobj(src, out, COPY_BUFFER)
        log.debug("%s: %d Dateien angehängt", target, len(ip_files))

    log.info("%d Handler-Logs zu %d Dateien zusammengeführt", len(files), len(by_ip))
