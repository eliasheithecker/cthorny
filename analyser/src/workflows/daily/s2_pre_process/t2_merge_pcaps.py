import logging
import shutil
import subprocess
from pathlib import Path

from utils import Context
from models.paths import WorkingFiles

log = logging.getLogger(__name__)

def merge_pcaps(ctx: Context) -> None:
    """Entpackt alle raw/**/*.pcap.gz und führt sie per mergecap zu einer PCAP zusammen.

    Die entpackten Dateien liegen nur während des Schritts in interim/tmp_pcap
    und werden nach dem Zusammenführen gelöscht.
    """
    output_file = ctx.workingPathOf(WorkingFiles.PCAPS_FILE)
    Path(output_file.parent).mkdir(parents=True, exist_ok=True)
    log.debug("ouput_dir created: %s", output_file.parent)
    log.debug("output_file: %s", output_file)

    if not ctx.force_reload and output_file.exists():
        log.info("PCAPs bereits zusammengeführt, überspringe Schritt")
        return

    tmp_dir = create_tmp_pcaps(ctx)

    ## mergecap
    # mergecap -w merged_all.pcap $(find tmp_pcaps -type f -name '*.pcap' | sort)
    tmp_pcaps = sorted(str(p) for p in tmp_dir.rglob("*.pcap") if p.is_file())
    log.debug("%d temporäre PCAPs werden zusammengeführt", len(tmp_pcaps))
    subprocess.run(["mergecap", "-w", str(output_file), *tmp_pcaps], check=True)
    log.info("%d PCAPs zu %s zusammengeführt", len(tmp_pcaps), output_file)

    # rm -R tmp_pcaps
    shutil.rmtree(tmp_dir)
    log.debug("tmp_dir gelöscht: %s", tmp_dir)



def create_tmp_pcaps(ctx: Context) -> Path:
    """Entpackt alle raw/**/*.pcap.gz per gunzip nach interim/tmp_pcap.

    Der Dateiname ist der Pfad relativ zu raw/ mit '_' statt '/', ohne .gz.
    """
    tmp_dir = ctx.workingPathOf(WorkingFiles.TMP_PCAPS_DIR)
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir) # rm -R tmp_pcaps
    
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    log.debug("tmp_dir created: %s", tmp_dir)

    raw_dir = ctx.workingPathOf(WorkingFiles.RAW_DIR)
    log.debug("raw_dir: %s", raw_dir)

    # for f in $(find raw -type f -name '*.pcap.gz')
    files = sorted(p for p in raw_dir.rglob("*.pcap.gz") if p.is_file())
    if len(files) == 0:
        log.error("Keine PCAPs gefunden")
        raise SystemExit(f"Keine PCAPs gefunden in {raw_dir}")
    log.debug("%d PCAPs gefunden", len(files))

    # gunzip -c "$f" > "$tmpname"
    for file in files:
        tmp_name = tmp_dir / str(file.relative_to(raw_dir)).replace("/", "_").removesuffix(".gz")
        with open(tmp_name, "wb") as out:
            subprocess.run(["gunzip", "-c", str(file)], stdout=out, check=True)
    log.debug("%d PCAPs entpackt nach %s", len(files), tmp_dir)
    
    return tmp_dir
