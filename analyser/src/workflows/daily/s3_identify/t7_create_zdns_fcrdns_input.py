import logging
from pathlib import Path
from pyspark.sql import functions as F

from utils import Context
from models.paths import WorkingFiles


log = logging.getLogger(__name__)


def create_zdns_FCrDNS_input(ctx: Context) -> None:
    output_file = ctx.workingPathOf(WorkingFiles.ZDNS_FCRDNS_INPUT)
    if not ctx.force_reload and output_file.exists():
        log.info("ZDNS FCrDNS input already created, skipping step")
        return

    Path(output_file.parent).mkdir(parents=True, exist_ok=True)
    log.debug("ouput_dir created: %s", output_file.parent)

    joined_file = ctx.workingPathOf(WorkingFiles.ALL_SCANNER_JOINED)
    log.debug("Loading joined scanners from %s", joined_file)

    # 1) Load joined scanners (output of t6_join_sources)
    # Ohne inferSchema sind alle Spalten string (spart einen Lesedurchgang);
    # passed_hostname_filter wird unten ohnehin als string verglichen.
    result_sdf = ctx.spark.read.csv(str(joined_file), sep="\t", header=True)

    # 2) Keep hostnames that are identified by editorial list, ISC
    #    or passed the keyword hostname filter
    has_hostname = F.col("hostname").isNotNull() & (F.trim(F.col("hostname")) != "")
    passed_filter = F.lower(F.col("passed_hostname_filter").cast("string")) == "true"
    is_identified = (
        F.col("editorial_id").isNotNull()
        | F.col("isc_id").isNotNull()
        | passed_filter
    )

    fcrdns_input_sdf = (
        result_sdf
        .filter(has_hostname & is_identified)
        .select("hostname")
        .dropDuplicates()
    )

    # 3) Construct required ZDNS format: hostname,,a-trigger
    fcrdns_input_sdf = fcrdns_input_sdf.select(
        F.concat(F.col("hostname"), F.lit(",,a-trigger")).alias("line")
    )

    # 4) Write as single file without header
    fcrdns_input_pdf = fcrdns_input_sdf.toPandas()
    with open(output_file, "w") as f:
        for line in fcrdns_input_pdf["line"]:
            f.write(f"{line}\n")

    log.info(
        "ZDNS FCrDNS input created: %s with %d entries",
        output_file,
        len(fcrdns_input_pdf),
    )
