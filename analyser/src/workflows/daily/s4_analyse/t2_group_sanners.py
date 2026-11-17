import logging
from pathlib import Path

from utils import Context, GROUP_KEY, UNKNOWN_ID, group_order
from models.paths import WorkingFiles

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

log = logging.getLogger(__name__)

PROTOCOLS = ["ssh", "telnet", "smtp", "ldap"]
LEVEL_COLUMNS = [
    f"{proto}_{level}_level"
    for proto in PROTOCOLS
    for level in ("transport", "application")
]


def group_scanners(ctx: Context) -> None:
    """
    Ordnet jede Scanner-IP einer Gruppe zu und schreibt zwei Tabellen, verknüpft über (id_source, id).

    Gruppierung (in dieser Priorität):
      1. editorial_id   (gewinnt immer, auch wenn zusätzlich eine isc_id existiert)
      2. isc_id         (nur wenn keine editorial_id vorhanden ist)
      3. alle übrigen IPs in der Gruppe "unknown" (nur wenn ctx.analyse_unkown, sonst verworfen)

    scanner_groups.tsv (eine Zeile pro Gruppe):
      id | id_source | ip_count | editorial_suffix | editorial_type | isc_ids |
      <proto>_transport_level | <proto>_application_level   (je Protokoll das Maximum der Gruppe)

    scanner_ips.tsv (eine Zeile pro IP):
      id | id_source | ip | hostname | dns_status | fcrdns_valid | isc_id
    """
    scanners_input_file = ctx.workingPathOf(WorkingFiles.ALL_SCANNER_JOINED_VALIDATED)
    event_levels_input_file = ctx.workingPathOf(WorkingFiles.EVENT_LEVELS)
    groups_output_file = ctx.workingPathOf(WorkingFiles.SCANNER_GROUPS)
    ips_output_file = ctx.workingPathOf(WorkingFiles.SCANNER_IPS)

    if not ctx.force_reload and groups_output_file.exists() and ips_output_file.exists():
        log.info("Scanner groups already exist, skipping step")
        return
    Path(groups_output_file.parent).mkdir(parents=True, exist_ok=True)
    log.debug("output_dir created: %s", groups_output_file.parent)

    scanners = load_scanners_with_group_id(ctx, scanners_input_file).cache()
    ensure_one_row_per_ip(scanners)
    events = read_tsv(ctx, event_levels_input_file)

    groups = (
        aggregate_group_fields(scanners)
        .join(aggregate_event_levels(scanners, events), on=GROUP_KEY, how="left")
        # Protokoll ohne Events in der Gruppe -> Level 0 ("No Connection" / "No Interaction")
        .fillna(0, subset=LEVEL_COLUMNS)
        .select(
            "id",
            "id_source",
            "ip_count",
            "editorial_suffix",
            "editorial_type",
            F.to_json("isc_ids").alias("isc_ids"),
            *LEVEL_COLUMNS,
        )
        .orderBy(group_order(), "id")
    )
    write_tsv(groups, groups_output_file)
    log.info("Scanner groups saved to %s", groups_output_file)

    write_tsv(scanner_ips(scanners), ips_output_file)
    log.info("Scanner IPs saved to %s", ips_output_file)
    scanners.unpersist()


def read_tsv(ctx: Context, path: Path) -> DataFrame:
    return (
        ctx.spark.read
        .option("header", "true")
        .option("delimiter", "\t")
        .csv(str(path))
    )


def write_tsv(df: DataFrame, path: Path) -> None:
    df.toPandas().to_csv(str(path), sep="\t", index=False, header=True)


def load_scanners_with_group_id(ctx: Context, path: Path) -> DataFrame:
    """
    Liest die Scanner und vergibt die Gruppen-ID: editorial_id > isc_id > unknown.
    Die Gruppe "unknown" bleibt nur erhalten, wenn ctx.analyse_unkown gesetzt ist.
    """
    scanners = read_tsv(ctx, path).select(
        "ip",
        "hostname",
        "dns_status",
        "editorial_suffix",
        "editorial_type",
        "isc_id",
        (F.lower(F.col("fcrdns_valid")) == "true").alias("fcrdns_valid"),
        F.coalesce("editorial_id", "isc_id", F.lit(UNKNOWN_ID)).alias("id"),
        F.when(F.col("editorial_id").isNotNull(), "editorial")
        .when(F.col("isc_id").isNotNull(), "isc")
        .otherwise(UNKNOWN_ID)
        .alias("id_source"),
    )

    if not ctx.analyse_unkown:
        log.info("analyse_unkown=False: Gruppe '%s' wird verworfen", UNKNOWN_ID)
        scanners = scanners.filter(F.col("id_source") != UNKNOWN_ID)
    return scanners


def ensure_one_row_per_ip(scanners: DataFrame) -> None:
    """t6_join_sources reduziert auf eine Zeile pro IP; scanner_ips.tsv verlässt sich darauf."""
    rows = scanners.count()
    ips = scanners.select("ip").distinct().count()
    if rows != ips:
        raise ValueError(f"Erwartet eine Zeile pro IP, gefunden: {rows} Zeilen für {ips} IPs")


def aggregate_group_fields(scanners: DataFrame) -> DataFrame:
    """Anzahl IPs, editorial_suffix und editorial_type als Einzelwert, isc_id als Liste (eindeutige Werte)."""
    return (
        scanners
        .groupBy(*GROUP_KEY)
        .agg(
            F.count("*").alias("ip_count"),
            F.first("editorial_suffix", ignorenulls=True).alias("editorial_suffix"),  # genau ein Suffix je editorial_id
            F.first("editorial_type", ignorenulls=True).alias("editorial_type"),  # genau ein Typ je editorial_id
            F.array_sort(F.collect_set("isc_id")).alias("isc_ids"),
        )
    )


def aggregate_event_levels(scanners: DataFrame, events: DataFrame) -> DataFrame:
    """Je Gruppe und Protokoll das Maximum von transport_level und application_level (wide format)."""
    return (
        events
        .join(scanners.select("ip", *GROUP_KEY), on="ip", how="inner")
        .groupBy(*GROUP_KEY)
        .pivot("protocol", PROTOCOLS)
        .agg(
            F.max(F.col("transport_level").cast("int")).alias("transport_level"),
            F.max(F.col("application_level").cast("int")).alias("application_level"),
        )
    )


def scanner_ips(scanners: DataFrame) -> DataFrame:
    """Eine Zeile pro IP mit ihrer Gruppe und den IP-eigenen DNS-/ISC-Werten."""
    return (
        scanners
        .select(
            "id",
            "id_source",
            "ip",
            "hostname",
            "dns_status",
            "fcrdns_valid",
            "isc_id",
        )
        .orderBy(group_order(), "id", "ip")
    )
