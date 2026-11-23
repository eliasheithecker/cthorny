import logging
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pathlib import Path


from utils import Context
from models.paths import WorkingFiles


log = logging.getLogger(__name__)


def validate_fcrdns(ctx: Context) -> None:
    output_file = ctx.workingPathOf(WorkingFiles.ALL_SCANNER_JOINED_VALIDATED)
    if not ctx.force_reload and output_file.exists():
        log.info("Validated joined sources already exist, skipping step")
        return
    Path(output_file.parent).mkdir(parents=True, exist_ok=True)
    log.debug("ouput_dir created: %s", output_file.parent)
    
    answers_sdf = flatten_zdns_fcrdns(ctx)

    # Deduplicate
    answers_sdf = answers_sdf.dropDuplicates()

    # Broadcast and add validation flag
    answers_sdf = F.broadcast(
        answers_sdf.withColumn("fcrdns_valid", F.lit(True))
    )

    result_sdf = load_result_sdf(ctx)

    # Left join on both hostname and ip
    result_sdf = result_sdf.join(
        answers_sdf,
        on=["hostname", "ip"],
        how="left"
    )

    # Replace NULL with False
    result_sdf = result_sdf.withColumn(
        "fcrdns_valid",
        F.coalesce(F.col("fcrdns_valid"), F.lit(False))
    )
    
    # 10) Write to TSV
    result_sdf.toPandas().to_csv(
        str(output_file),
        sep="\t",
        index=False,
        header=True
    )
    log.info("Joined sources saved to %s", output_file)
    
        

# Nur die benötigten Felder der ZDNS-Ausgabe. Das explizite Schema spart die
# Schema-Erkennung und liefert auch bei leerer Datei joinbare Spalten.
ZDNS_A_SCHEMA = (
    "name STRING, "
    "results STRUCT<A: STRUCT<status: STRING, data: STRUCT<answers: ARRAY<STRUCT<answer: STRING>>>>>"
)


def flatten_zdns_fcrdns(ctx: Context) -> DataFrame:
    raw_file = ctx.workingPathOf(WorkingFiles.ALL_SCANNER_FCRDNS_RECORDS_RAW)
    log.debug("Loading ZDNS FCrDNS records from %s", raw_file)

    # Eine Zeile pro (hostname, answer) aus allen NOERROR-Antworten
    return (
        ctx.spark.read.schema(ZDNS_A_SCHEMA).json(str(raw_file))
        .filter(F.col("results.A.status") == "NOERROR")
        .select(
            F.col("name").alias("hostname"),
            F.explode("results.A.data.answers").alias("answer"),
        )
        .select("hostname", F.col("answer.answer").alias("ip"))
    )


def load_result_sdf(ctx: Context) -> DataFrame:
    joined_file = ctx.workingPathOf(WorkingFiles.ALL_SCANNER_JOINED)
    log.debug("Loading joined scanners from %s", joined_file)

    # 1) Load joined scanners (output of t6_join_sources)
    return ctx.spark.read.csv(str(joined_file), sep="\t", header=True)
    