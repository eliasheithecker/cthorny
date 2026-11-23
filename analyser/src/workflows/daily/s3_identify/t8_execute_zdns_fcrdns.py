import logging
import subprocess
from importlib.resources import as_file, files
from pathlib import Path

from utils import Context, execute_zdns
from models.paths import WorkingFiles

log = logging.getLogger(__name__)

def execute_zdns_fcrdns(ctx: Context) -> None:
    """Fragt die PTR-Records aller Client-IPs per zdns MULTIPLE ab (Schritt 5)."""
    output_file = ctx.workingPathOf(WorkingFiles.ALL_SCANNER_FCRDNS_RECORDS_RAW)
    if not ctx.force_reload and output_file.exists():
        log.info("ZDNS PTR execution already done, skipping step")
        return

    Path(output_file.parent).mkdir(parents=True, exist_ok=True)
    log.debug("ouput_dir created: %s", output_file.parent)

    input_file = ctx.workingPathOf(WorkingFiles.ZDNS_FCRDNS_INPUT)
    log_file = ctx.workingPathOf(WorkingFiles.ZDNS_FCRDNS_LOG)

    execute_zdns(input_file, output_file, log_file)
    
    log.info("PTR-Records gespeichert in %s (zdns-Log: %s)", output_file, log_file)
