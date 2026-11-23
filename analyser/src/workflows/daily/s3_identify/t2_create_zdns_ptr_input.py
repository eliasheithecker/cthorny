import logging
from collections import defaultdict, deque
from pathlib import Path
import pandas as pd

from utils import Context
from models.paths import WorkingFiles


log = logging.getLogger(__name__)


def create_zdns_ptr_input(ctx: Context) -> None:
    output_file = ctx.workingPathOf(WorkingFiles.ZDNS_RDNS_INPUT_ALL)
    if not ctx.force_reload and output_file.exists():
        log.info("ZDNS PTR input already created, skipping step")
        return
    
    Path(output_file.parent).mkdir(parents=True, exist_ok=True)
    log.debug("ouput_dir created: %s", output_file.parent)
    
    handlers_input_dir = ctx.workingPathOf(WorkingFiles.HANDLER_FLAT_HEADERS_DIR)
    log.debug("handlers_input_dir: %s", handlers_input_dir)
    half_open_scanners_file = ctx.workingPathOf(WorkingFiles.HALF_OPEN_SCANNERS)
    log.debug("half_open_scanners_file: %s", half_open_scanners_file)
    
    # 1. Read handler logs + extract client_ip
    # Explizites Schema: Spark liest nur client_ip und muss das Schema
    # der (sehr breiten) Handler-Logs nicht erst über alle Dateien ermitteln.
    handler_ips = (
        ctx.spark.read.schema("client_ip STRING").json(str(handlers_input_dir))
        .select("client_ip")
        .dropna()
        .distinct()
        .toPandas()["client_ip"]
    )
    log.debug(f"[checkpoint] Unique IPs in handlers dir: {len(handler_ips)}")

    # 2. Read half-open scanner IPs
    half_open_ips = (
        pd.read_csv(str(half_open_scanners_file), sep="\t", header=None)[0]
        .dropna()
        .unique()
    )

    log.debug(f"[checkpoint] Unique IPs in half_open_scanners.tsv: {len(half_open_ips)}")

    # 3. Combine both sources + remove duplicates
    all_unique_ips = pd.Series(
        list(handler_ips) + list(half_open_ips)
    ).drop_duplicates()

    log.debug(f"[checkpoint] Total unique IPs combined: {len(all_unique_ips)}")

    # 4. Create ZDNS input format
    rDNS_list = pd.DataFrame({
        "client_ip": all_unique_ips,
        "empty": "",
        "trigger": "ptr-trigger"
    })

    # 5. Write CSV
    rDNS_list.to_csv(
        str(output_file),
        sep=",",
        index=False,
        header=False
    )
    
    log.info(f"ZDNS PTR input created: {output_file} with {len(rDNS_list)} entries")

    
    
    
    
    
    