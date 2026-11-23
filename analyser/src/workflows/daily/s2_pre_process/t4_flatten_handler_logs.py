import logging

from pathlib import Path
import pandas as pd
import json
import glob
import os
import shutil
from datetime import datetime, timezone

from utils import Context
from models.paths import WorkingFiles

log = logging.getLogger(__name__)

# Wenn True, werden nur Handler-Logs übernommen, deren Sitzungsstart ("ts", Unix-Sekunden)
# in UTC auf ctx.date_of_data fällt. Logs ohne gültiges "ts" werden dann verworfen.
FILTER_BY_DATE = True


def flatten_handler_logs(ctx: Context) -> None:
    flatten_headers_in_logs(ctx)
    extract_logs_per_protocol(ctx)
    
def extract_logs_per_protocol(ctx: Context) -> None:
    if not ctx.force_reload and all(ctx.workingPathOf(f).is_file() for f in [
        WorkingFiles.HANDLER_LOGS_SSH,
        WorkingFiles.HANDLER_LOGS_SMTP,
        WorkingFiles.HANDLER_LOGS_TELNET,
        WorkingFiles.HANDLER_LOGS_LDAP
    ]):
        log.info("Handler logs per protocol already extracted, skipping step")
        return
    
    log.debug("Extracting logs per protocol from %s", ctx.workingPathOf(WorkingFiles.HANDLER_FLAT_HEADERS_DIR))
    
    # Einmal mit Spark einlesen (JSONL, Schema über alle Dateien) und cachen.
    # Nach Protokoll wird noch in Spark gefiltert: so enthalten die Spalten der Teilmenge
    # keine Lücken aus anderen Protokollen und pandas behält int/bool statt float/object.
    sdf = ctx.spark.read.json(
        str(ctx.workingPathOf(WorkingFiles.HANDLER_FLAT_HEADERS_DIR))
    ).cache()

    for name, protocol, target in [
        ("SSH", "ssh", WorkingFiles.HANDLER_LOGS_SSH),
        ("Telnet", "telnet", WorkingFiles.HANDLER_LOGS_TELNET),
        ("LDAP", "ldap", WorkingFiles.HANDLER_LOGS_LDAP),
        ("SMTP", "smtp", WorkingFiles.HANDLER_LOGS_SMTP),
    ]:
        df = sdf.filter(sdf["protocol"] == protocol).toPandas().dropna(axis=1, how='all')
        if protocol != "ldap":
            df = df.rename(columns={"duration": "duration_ms"})

        path = ctx.workingPathOf(target)
        write_single_jsonl(df, path)
        log.debug("%s logs saved to %s", name, path)

    sdf.unpersist()

    log.info("Handler logs extracted per protocol and saved.")


def write_single_jsonl(df: pd.DataFrame, path: Path) -> None:
    """Schreibt df als eine einzelne JSONL-Datei (statt Spark-part-Verzeichnis)."""
    if path.is_dir():
        # Altlast aus früheren Läufen: Spark hat hier ein part-Verzeichnis angelegt
        shutil.rmtree(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_json(
        str(path),
        orient="records",
        lines=True,
        force_ascii=False,
    )

def flatten_headers_in_logs(ctx: Context) -> None:
    output_dir = ctx.workingPathOf(WorkingFiles.HANDLER_FLAT_HEADERS_DIR)
    if not ctx.force_reload and output_dir.exists() and any(output_dir.iterdir()):
        log.info("Handler-Logs bereits abgeflacht, überspringe Schritt")
        return
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    log.debug("ouput_dir created: %s", output_dir)
    
    glob_pattern = str(ctx.workingPathOf(WorkingFiles.HANDLERS_DIR)) + "/*.jsonl"
    log.debug("glob_pattern: %s", glob_pattern)
    
    # Process all JSONL files in the handlers directory
    for filepath in glob.glob(glob_pattern):
        filename = os.path.basename(filepath)
        output_path = os.path.join(output_dir, filename)
        
        log.debug("Processing file: %s", filepath)
        
        # Read all records
        records = []
        dropped = 0
        with open(filepath, 'r') as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    if FILTER_BY_DATE and not is_on_date(record, ctx.date_of_data):
                        dropped += 1
                        continue
                    records.append(flatten_headers(record))
        
        if FILTER_BY_DATE:
            log.debug("Dropped %d records not from %s in %s", dropped, ctx.date_of_data, filename)
        log.debug("Flattened headers in %s", filename)
        # Write to new directory
        with open(output_path, 'w') as f:
            for record in records:
                f.write(json.dumps(record, separators=(',', ':'), ensure_ascii=False) + '\n')
        
        log.debug("Completed %s -> %s", filename, output_path)
    log.info(f"\nAll files processed to {output_dir}/")

def is_on_date(record, day) -> bool:
    """True, wenn der Sitzungsstart ("ts", Unix-Sekunden) in UTC auf `day` fällt."""
    ts = record.get('ts')
    if not isinstance(ts, (int, float)):
        return False
    return datetime.fromtimestamp(ts, tz=timezone.utc).date() == day

def flatten_headers(record):
    """Convert headers dict to list of 'Key: Value' strings"""
    if 'headers' in record and isinstance(record['headers'], dict):
        record['headers'] = [f"{k}: {v}" for k, v in record['headers'].items()]
    return record