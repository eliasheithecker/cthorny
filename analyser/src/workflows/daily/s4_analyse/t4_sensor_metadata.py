import logging
from pathlib import Path

from utils import Context
from models.paths import WorkingFiles

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from .t3_analyse_traffic import read_connection_attempts, read_half_open_events

log = logging.getLogger(__name__)

# Spalten von descriptors.csv (ohne Header), siehe s2_pre_process/t3_extract_sensors.
# Die Reihenfolge ergibt sich aus dem von Spark alphabetisch inferierten JSON-Schema.
DESCRIPTOR_COLUMNS = [
    "creation", "hostname", "ipv4", "ipv6", "os", "provider", "region", "source_path", "ip_from_dir",
]
# In die Ausgabe übernommene Descriptor-Felder (source_path/ip_from_dir sind lokale Hilfsspalten)
DESCRIPTOR_FIELDS = ["hostname", "ipv4", "ipv6", "creation", "os", "provider", "region"]
DESCRIPTOR_KEY = ["ipv4", "creation"]


def sensor_metadata(ctx: Context) -> None:
    """
    Erweitert die Sensor-Descriptoren um die Verbindungen, die am Sensor ankamen.

    Zählweise wie in t3_analyse_traffic: Jedes SYN ohne ACK-Flag ist ein Verbindungsversuch,
    halboffen sind die SYNs aus half_open_events (kein ACK innerhalb von FLOW_TIMEOUT),
    voll (mit ACK) ist der Rest.

    Zuordnung: Eine Sensor-IP kann über die Zeit mehrere Descriptoren haben (Spot-Instanzen).
    Ein Paket gehört zu dem Descriptor derselben IP, dessen creation zuletzt vor dem Paket liegt.

    Ausgabe (eine Zeile pro Descriptor):
      hostname | ipv4 | ipv6 | creation | os | provider | region |
      connections_total | connections_full | connections_half_open
    Sensoren ohne Verbindungen bekommen 0.
    """
    descriptors_input_file = ctx.workingPathOf(WorkingFiles.SENSORS_DESCRIPTORS)
    handshake_input_file = ctx.workingPathOf(WorkingFiles.TCP_HANDSHAKE_MIN)
    half_open_events_input_file = ctx.workingPathOf(WorkingFiles.HALF_OPEN_EVENTS)
    output_file = ctx.workingPathOf(WorkingFiles.SENSORS_METADATA)

    if not ctx.force_reload and output_file.exists():
        log.info("Sensor metadata already exists, skipping step")
        return
    Path(output_file.parent).mkdir(parents=True, exist_ok=True)
    log.debug("output_dir created: %s", output_file.parent)

    descriptors = load_descriptors(ctx, descriptors_input_file)

    connections = assign_to_descriptor(
        read_connection_attempts(ctx, handshake_input_file), descriptors, "connection attempts"
    )
    half_open = assign_to_descriptor(
        read_half_open_events(ctx, half_open_events_input_file), descriptors, "half-open events"
    )

    totals = connections.groupBy(*DESCRIPTOR_KEY).agg(F.count("*").alias("connections_total"))
    half_open_totals = half_open.groupBy(*DESCRIPTOR_KEY).agg(F.count("*").alias("connections_half_open"))

    result = (
        descriptors
        .join(totals, on=DESCRIPTOR_KEY, how="left")
        .join(half_open_totals, on=DESCRIPTOR_KEY, how="left")
        # Sensor ohne Verbindungen -> 0
        .fillna(0, subset=["connections_total", "connections_half_open"])
        .withColumn("connections_full", F.col("connections_total") - F.col("connections_half_open"))
        .select(
            *DESCRIPTOR_FIELDS,
            "connections_total",
            "connections_full",
            "connections_half_open",
        )
        .orderBy(F.col("connections_total").desc(), "ipv4", "creation")
    )

    result.toPandas().to_csv(
        str(output_file),
        sep="\t",
        index=False,
        header=True,
    )
    log.info("Sensor metadata saved to %s", output_file)


def load_descriptors(ctx: Context, path: Path) -> DataFrame:
    """
    Liest descriptors.csv und ergänzt den Gültigkeitszeitraum je Descriptor:
    [creation, creation des nächsten Descriptors derselben IP), nach oben offen für den letzten.
    """
    creation_us = F.unix_micros(F.to_timestamp("creation"))
    next_creation_us = F.lead("valid_from_us").over(Window.partitionBy("ipv4").orderBy("valid_from_us"))
    return (
        ctx.spark.read
        .option("header", "false")
        .csv(str(path))
        .toDF(*DESCRIPTOR_COLUMNS)
        .select(*DESCRIPTOR_FIELDS)
        .withColumn("valid_from_us", creation_us)
        .withColumn("valid_until_us", next_creation_us)
    )


def assign_to_descriptor(events: DataFrame, descriptors: DataFrame, label: str) -> DataFrame:
    """Hängt an jedes Event den Schlüssel des zum Zeitpunkt gültigen Descriptors seiner Sensor-IP."""
    d = F.broadcast(
        descriptors.select(
            F.col("ipv4").alias("d_ipv4"), "creation", "valid_from_us", "valid_until_us"
        )
    )
    in_range = (
        (F.col("sensor_ip") == F.col("d_ipv4"))
        & (F.col("ts_us") >= F.col("valid_from_us"))
        & (F.col("valid_until_us").isNull() | (F.col("ts_us") < F.col("valid_until_us")))
    )
    joined = events.join(d, on=in_range, how="left")

    unassigned = joined.filter(F.col("d_ipv4").isNull()).count()
    if unassigned:
        log.warning("%d %s ohne passenden Sensor-Descriptor werden ignoriert", unassigned, label)

    return (
        joined
        .filter(F.col("d_ipv4").isNotNull())
        .select(F.col("d_ipv4").alias("ipv4"), "creation")
    )

