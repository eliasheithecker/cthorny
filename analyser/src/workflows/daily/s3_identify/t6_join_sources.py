from importlib.resources import files
import logging
from pathlib import Path
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from utils import Context, filter_hostnames
from models.paths import WorkingFiles

log = logging.getLogger(__name__)

EDITORIAL_SCANNERS_FILE = files(__package__) / "scanners.csv"

def join_sources(ctx: Context) -> None:
    output_file = ctx.workingPathOf(WorkingFiles.ALL_SCANNER_JOINED)
    if not ctx.force_reload and output_file.exists():
        log.info("Joined sources already exist, skipping step")
        return
    Path(output_file.parent).mkdir(parents=True, exist_ok=True)
    log.debug("ouput_dir created: %s", output_file.parent)
    
    # 1) Load rDNS JSONL
    rdns_sdf = load_rDns(ctx)

    # 2) Load scanners.csv (klein -> broadcast)
    editorial_scanners_sdf = F.broadcast(load_editorial_scanners(ctx))

    # 3) Load ISC Research scanners (klein -> broadcast)
    isc_sdf = F.broadcast(load_isc_research_scanners(ctx))

    rdns_sdf = rdns_sdf.withColumn(
        "hostname",
        F.lower(F.col("hostname"))
    )

    # 4) Suffix join
    joined_sdf = rdns_sdf.join(
        editorial_scanners_sdf,
        rdns_sdf["hostname"].endswith(editorial_scanners_sdf["suffix"]),
        how="left"
    )

    # 5) Clean + rename
    result_sdf = (
        joined_sdf
        .withColumnRenamed("id", "editorial_id")
        .withColumnRenamed("suffix", "editorial_suffix")
        .withColumnRenamed("type", "editorial_type")
    )

    # 6) Keep only IPv4
    ipv4_regex = r'^\d{1,3}(\.\d{1,3}){3}$'
    result_sdf = result_sdf.filter(
        F.col("ip").rlike(ipv4_regex)
    )

    # 7) Resolve to ONE ROW PER IP
    window = Window.partitionBy("ip").orderBy(
        F.col("editorial_id").isNotNull().desc(),  # prefer matches
        F.length("hostname").desc()
    )

    result_sdf = (
        result_sdf
        .withColumn("rank", F.row_number().over(window))
        .filter(F.col("rank") == 1)
        .drop("rank")
    )

    # Join isc research scanners
    result_sdf = result_sdf.join(
        isc_sdf,
        on="ip",
        how="left"
    )

    # Rename column
    result_sdf = result_sdf.withColumnRenamed("status", "dns_status")

    # 8) Flag rows whose hostname passes the keyword/exclude filter
    result_sdf = filter_hostnames(result_sdf)

    # 9) Sort: editorial match -> ISC match -> hostname (filter passed)
    #    -> hostname (filter not passed) -> IP only
    has_hostname = F.col("hostname").isNotNull() & (F.trim(F.col("hostname")) != "")
    sort_group = (
        F.when(F.col("editorial_id").isNotNull(), 0)
        .when(F.col("isc_id").isNotNull(), 1)
        .when(F.col("passed_hostname_filter"), 2)
        .when(has_hostname, 3)
        .otherwise(4)
    )
    result_sdf = result_sdf.orderBy(
        sort_group,
        F.col("editorial_id").asc_nulls_last(),
        F.col("isc_id").asc_nulls_last(),
        F.col("hostname").asc_nulls_last(),
        F.col("ip"),
    )

    # 10) Write to TSV
    result_sdf.toPandas().to_csv(
        str(output_file),
        sep="\t",
        index=False,
        header=True
    )
    log.info("Joined sources saved to %s", output_file)

def load_rDns(ctx: Context) -> DataFrame:
    rdns_record_file = ctx.workingPathOf(WorkingFiles.ALL_SCANNER_PTR_RECORDS_FLAT)
    log.debug("Loading rDNS JSONL from %s", rdns_record_file)
    return (
        ctx.spark.read.json(str(rdns_record_file))
        .withColumn("hostname", F.col("hostname").cast("string"))
        .withColumn("ip", F.col("ip").cast("string"))
    )

def load_editorial_scanners(ctx: Context) -> DataFrame:
    log.debug("Loading scanners.csv from %s", EDITORIAL_SCANNERS_FILE)
    # Ohne inferSchema liest Spark alle Spalten als string
    return (
        ctx.spark.read.csv(str(EDITORIAL_SCANNERS_FILE), sep=";", header=True)
        .select("id", "suffix", "type")
    )

def load_isc_research_scanners(ctx: Context) -> DataFrame:
    # Datei wird in t5 mit Kopfzeile geschrieben: ip, first_seen, last_seen, isc_id
    isc_sdf = ctx.spark.read.csv(
        str(ctx.workingPathOf(WorkingFiles.ISC_RESEARCH_SCANNER)),
        sep="\t",
        header=True
    )

    # Replace 'internetmeasurement' -> 'driftnet'
    isc_sdf = isc_sdf.withColumn(
        "isc_id",
        F.when(F.col("isc_id") == "internetmeasurement", "driftnet").otherwise(F.col("isc_id"))
    )

    # Keep only relevant columns and remove duplicate IPs
    return isc_sdf.select("ip", "isc_id").dropDuplicates(["ip"])
