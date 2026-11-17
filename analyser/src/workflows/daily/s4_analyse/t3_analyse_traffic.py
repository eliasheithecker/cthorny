import logging
from pathlib import Path

from utils import Context, GROUP_KEY, group_order
from models.paths import WorkingFiles

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

log = logging.getLogger(__name__)

# Gleitendes Fenster [t, t + 1h) in Mikrosekunden. rangeBetween ist an beiden
# Enden inklusiv, daher -1 µs, damit ein Event genau bei t + 1h nicht mitzählt.
ONE_HOUR_US = 3600 * 1_000_000
WINDOW_END_US = ONE_HOUR_US - 1

# Spalten von tcp_handshake_min.tsv (ohne Header), siehe TSHARK_FIELDS in t5_filter_pcap
HANDSHAKE_COLUMNS = ["timestamp", "ip", "sensor_ip", "src_port", "sensor_port", "flags"]
TCP_SYN = 0x02
TCP_ACK = 0x10
# Spalten von half_open_events.tsv (ohne Header), siehe t1_identify_half_open_scanners
HALF_OPEN_COLUMNS = ["timestamp", "ip", "src_port", "sensor_ip", "sensor_port"]

# Kennzahlen je Gruppe, in Ausgabereihenfolge; Gruppen ohne Verbindungen bekommen 0
COUNT_COLUMNS = [
    "connections_total",
    "connections_full",
    "connections_half_open",
    "max_conn_per_sensor_port_day",
    "max_conn_per_sensor_port_1h",
    "max_conn_per_sensor_day",
    "max_conn_per_sensor_1h",
    "max_conn_per_scanner_instance_per_sensor_port_day",
    "max_conn_per_scanner_instance_per_sensor_port_1h",
    "max_conn_per_scanner_instance_per_sensor_day",
    "max_conn_per_scanner_instance_per_sensor_1h",
]


def analyse_traffic(ctx: Context) -> None:
    """
    Wertet je Scanner-Gruppe alle Verbindungen (volle und halboffene) aus tcp_handshake_min aus.

    Jede Verbindung beginnt mit einem SYN (ohne ACK) der Quell-IP an einen Sensor
    (Dest-IP = Sensor) und Port. Gezählt wird daher jedes SYN-Paket, unabhängig davon,
    ob der Handshake danach abgeschlossen wurde. Reine ACK-Pakete gehören zu einer
    bereits gezählten Verbindung und werden verworfen. Die Quell-IPs einer Gruppe
    stammen aus scanner_ips.tsv (t2_group_sanners); die Gruppe "unknown" wird nur
    ausgewertet, wenn sie dort enthalten ist (ctx.analyse_unkown).

    Aufteilung voll / halboffen: Halboffen sind die SYNs aus half_open_events
    (t1_identify_half_open_scanners: kein ACK innerhalb von FLOW_TIMEOUT), voll ist der Rest.

    Ausgabe (eine Zeile pro Gruppe, Schlüssel id + id_source wie in scanner_groups.tsv):
      id | id_source | scanned_ips |
      connections_total | connections_full | connections_half_open |
      max_conn_per_sensor_port_day                   | max_conn_per_sensor_port_1h |
      max_conn_per_sensor_day                        | max_conn_per_sensor_1h |
      max_conn_per_scanner_instance_per_sensor_port_day | max_conn_per_scanner_instance_per_sensor_port_1h |
      max_conn_per_scanner_instance_per_sensor_day      | max_conn_per_scanner_instance_per_sensor_1h

    scanned_ips: JSON-Liste (sortiert, eindeutig) der Sensor-IPs, die die Gruppe kontaktiert hat.
    max_conn_per_sensor*: alle IPs der Gruppe zusammen auf einen Sensor (+ Port).
    max_conn_per_scanner_instance_per_sensor*: eine einzelne IP der Gruppe auf einen Sensor (+ Port).
    Die *_day-Werte zählen über den ganzen Tag, die *_1h-Werte sind das Maximum über ein
    gleitendes 60-Minuten-Fenster [t, t + 1h).
    Gruppen ohne Events bekommen 0 bzw. eine leere Liste.
    """
    scanner_ips_input_file = ctx.workingPathOf(WorkingFiles.SCANNER_IPS)
    handshake_input_file = ctx.workingPathOf(WorkingFiles.TCP_HANDSHAKE_MIN)
    half_open_events_input_file = ctx.workingPathOf(WorkingFiles.HALF_OPEN_EVENTS)
    output_file = ctx.workingPathOf(WorkingFiles.SCANNER_GROUPS_TRAFFIC)

    if not ctx.force_reload and output_file.exists():
        log.info("Scanner group traffic already exists, skipping step")
        return
    Path(output_file.parent).mkdir(parents=True, exist_ok=True)
    log.debug("output_dir created: %s", output_file.parent)

    ip_to_group = load_ip_to_group(ctx, scanner_ips_input_file).cache()
    # jede Gruppe hat mindestens eine IP, daher fehlt hier keine Gruppe
    groups = ip_to_group.select(*GROUP_KEY).distinct()

    events = (
        read_connection_attempts(ctx, handshake_input_file)
        .join(F.broadcast(ip_to_group), on="ip", how="inner")
        .cache()
    )

    half_open = (
        read_half_open_events(ctx, half_open_events_input_file)
        .join(F.broadcast(ip_to_group), on="ip", how="inner")
        .groupBy(*GROUP_KEY)
        .agg(F.count("*").alias("connections_half_open"))
    )

    metrics = (
        events
        .groupBy(*GROUP_KEY)
        .agg(
            F.array_sort(F.collect_set("sensor_ip")).alias("scanned_ips"),
            F.count("*").alias("connections_total"),
        )
        .join(half_open, on=GROUP_KEY, how="left")
        .fillna(0, subset=["connections_half_open"])
        .withColumn("connections_full", F.col("connections_total") - F.col("connections_half_open"))
        .join(max_connections(events, ["sensor_ip", "sensor_port"], "max_conn_per_sensor_port"), on=GROUP_KEY, how="left")
        .join(max_connections(events, ["sensor_ip"], "max_conn_per_sensor"), on=GROUP_KEY, how="left")
        .join(
            max_connections(events, ["ip", "sensor_ip", "sensor_port"], "max_conn_per_scanner_instance_per_sensor_port"),
            on=GROUP_KEY,
            how="left",
        )
        .join(
            max_connections(events, ["ip", "sensor_ip"], "max_conn_per_scanner_instance_per_sensor"),
            on=GROUP_KEY,
            how="left",
        )
    )

    result = (
        groups
        .join(metrics, on=GROUP_KEY, how="left")
        # Gruppe ohne Verbindungen -> 0
        .fillna(0, subset=COUNT_COLUMNS)
        .select(
            "id",
            "id_source",
            F.to_json(F.coalesce("scanned_ips", F.array().cast("array<string>"))).alias("scanned_ips"),
            *COUNT_COLUMNS,
        )
        .orderBy(group_order(), "id")
    )

    result.toPandas().to_csv(
        str(output_file),
        sep="\t",
        index=False,
        header=True,
    )
    events.unpersist()
    ip_to_group.unpersist()
    log.info("Scanner group traffic saved to %s", output_file)


def load_ip_to_group(ctx: Context, path: Path) -> DataFrame:
    """Liest scanner_ips.tsv (eine Zeile pro IP) als Zuordnung ip -> (id_source, id)."""
    return (
        ctx.spark.read
        .option("header", "true")
        .option("delimiter", "\t")
        .csv(str(path))
        .select("ip", *GROUP_KEY)
    )


def read_connection_attempts(ctx: Context, path: Path) -> DataFrame:
    """
    Liest tcp_handshake_min.tsv (ohne Header: timestamp, src_ip, dst_ip, src_port, dst_port, flags)
    und behält nur Verbindungsaufbauten: SYN gesetzt, ACK nicht gesetzt (auch ECN-SYNs wie 0x00c2).
    """
    flags = F.conv(F.regexp_replace("flags", "^0x", ""), 16, 10).cast("int")
    return (
        ctx.spark.read
        .option("delimiter", "\t")
        .csv(str(path))
        .toDF(*HANDSHAKE_COLUMNS)
        .filter((flags.bitwiseAND(TCP_SYN) != 0) & (flags.bitwiseAND(TCP_ACK) == 0))
        .select(
            "ip",
            "sensor_ip",
            "sensor_port",
            (F.col("timestamp").cast("double") * 1_000_000).cast("long").alias("ts_us"),
        )
    )


def read_half_open_events(ctx: Context, path: Path) -> DataFrame:
    """half_open_events.tsv: je Zeile ein SYN ohne ACK innerhalb von FLOW_TIMEOUT."""
    return (
        ctx.spark.read
        .option("delimiter", "\t")
        .csv(str(path))
        .toDF(*HALF_OPEN_COLUMNS)
        .select(
            "ip",
            "sensor_ip",
            "sensor_port",
            (F.col("timestamp").cast("double") * 1_000_000).cast("long").alias("ts_us"),
        )
    )


def max_connections(events: DataFrame, keys: list[str], name: str) -> DataFrame:
    """
    Je Gruppe das Maximum der Verbindungen über alle Ausprägungen von `keys`
    (z. B. Sensor, Sensor + Port oder Quell-IP + Sensor):
      <name>_day – insgesamt am Tag
      <name>_1h  – innerhalb eines gleitenden 60-Minuten-Fensters [t, t + 1h)
    """
    partition = [*GROUP_KEY, *keys]

    overall = (
        events
        .groupBy(*partition)
        .agg(F.count("*").alias("n"))
        .groupBy(*GROUP_KEY)
        .agg(F.max("n").alias(f"{name}_day"))
    )

    # Für jedes Event: Anzahl Events derselben Partition in [t, t + 1h).
    # Das Maximum davon ist das Maximum über alle gleitenden Fenster, da ein
    # maximales Fenster o. B. d. A. bei einem Event beginnt.
    hour_window = (
        Window.partitionBy(*partition)
        .orderBy("ts_us")
        .rangeBetween(0, WINDOW_END_US)
    )
    hourly = (
        events
        .withColumn("n_1h", F.count("*").over(hour_window))
        .groupBy(*GROUP_KEY)
        .agg(F.max("n_1h").alias(f"{name}_1h"))
    )

    return overall.join(hourly, on=GROUP_KEY, how="inner")
