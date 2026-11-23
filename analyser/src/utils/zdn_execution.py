import logging
import subprocess
from importlib.resources import as_file, files
from pathlib import Path

from utils import Context
from models.paths import WorkingFiles

log = logging.getLogger(__name__)

# multiple.ini liegt im Paket neben dieser Datei
MULTIPLE_INI = files(__package__) / "multiple.ini"

ZDNS_RESULT_VERBOSITY = "short"
ZDNS_INCLUDE_FIELDS = ["answer"]
ZDNS_NAME_SERVERS = ["1.1.1.1", "1.0.0.1"]
ZDNS_THREADS = 50
ZDNS_RETRIES = 3
ZDNS_TIMEOUT = 10  # Sekunden

def execute_zdns(input_file: Path, output_file: Path, log_file: Path) -> None:
    # erst in eine .part-Datei schreiben, damit ein abgebrochener Lauf nicht als fertig gilt
    part_file = output_file.with_name(output_file.name + ".part")
    with as_file(MULTIPLE_INI) as multiple_ini:
        command = [
            "zdns", "MULTIPLE",
            f"--multi-config-file={multiple_ini}",
            f"--input-file={input_file}",
            f"--output-file={part_file}",
            f"--result-verbosity={ZDNS_RESULT_VERBOSITY}",
            f"--include-fields={','.join(ZDNS_INCLUDE_FIELDS)}",
            f"--name-servers={','.join(ZDNS_NAME_SERVERS)}",
            f"--threads={ZDNS_THREADS}",
            f"--retries={ZDNS_RETRIES}",
            f"--timeout={ZDNS_TIMEOUT}",
            f"--log-file={log_file}",
        ]
        log.debug("zdns command: %s", command)
        subprocess.run(command, check=True)

    part_file.replace(output_file)
    log.debug("PTR-Records gespeichert in %s (zdns-Log: %s)", output_file, log_file)
