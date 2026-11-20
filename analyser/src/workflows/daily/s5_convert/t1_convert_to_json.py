import csv
import datetime as dt
import json
import logging
from dataclasses import fields
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from models import (
    APPLICATION_LEVELS,
    SCHEMA_VERSION,
    DailyActor,
    DailyResult,
    DailyScannerInstance,
    DailySensor,
    DailyTraffic,
    Protocol,
    ProtocolResult,
    TransportLevel,
)
from models.paths import WorkingFiles
from utils import Context, GROUP_KEY, UNKNOWN_ID, group_order, write_json

log = logging.getLogger(__name__)

# Felder einer Scanner-Instanz aus scanner_ips.tsv; ip zuerst, damit array_sort nach ip sortiert
INSTANCE_COLUMNS = ["ip", "hostname", "dns_status", "fcrdns_valid", "isc_id"]


def convert_to_json(ctx: Context) -> None:
    """
    Führt die Ausgaben von s4 zu einem DailyResult zusammen und speichert es als JSON:
      scanner_groups.tsv + scanner_ips.tsv + scanner_groups_traffic.tsv -> actors (Join über id_source + id)
      sensor_metadata.tsv                                               -> sensors
    """
    sensors_input_file = ctx.workingPathOf(WorkingFiles.SENSORS_METADATA)
    output_file = ctx.workingPathOf(WorkingFiles.DAILY_RESULT_JSON)

    if not ctx.force_reload and output_file.exists():
        log.info("Daily result already exists, skipping step")
        return
    result = DailyResult(
        schema_version=SCHEMA_VERSION,
        date=ctx.date_of_data,
        generated_at=dt.datetime.now(dt.UTC),
        sensors=[parse_sensor(row) for row in read_tsv(sensors_input_file)],
        actors=[parse_actor(row) for row in load_actor_rows(ctx)],
    )

    write_json(result, output_file)
    log.info(
        "Daily result with %d sensors and %d actors saved to %s",
        len(result.sensors), len(result.actors), output_file,
    )


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def read_spark_tsv(ctx: Context, file: WorkingFiles) -> DataFrame:
    return (
        ctx.spark.read
        .option("header", "true")
        .option("delimiter", "\t")
        # isc_ids ist ein JSON-Array in Anführungszeichen mit verdoppelten Quotes ("")
        .option("quote", '"')
        .option("escape", '"')
        .csv(str(ctx.workingPathOf(file)))
    )


def load_actor_rows(ctx: Context) -> list[dict[str, Any]]:
    """
    Eine Zeile pro Gruppe: alle Spalten aus scanner_groups.tsv und scanner_groups_traffic.tsv
    plus instances (Liste der IPs aus scanner_ips.tsv, nach ip sortiert).
    Die Gruppe "unknown" bekommt keine instances: ihre IP-Liste ist zu groß für die Tagesdatei,
    die Details pro IP stehen weiterhin in scanner_ips.tsv.
    """
    groups = read_spark_tsv(ctx, WorkingFiles.SCANNER_GROUPS)
    traffic = read_spark_tsv(ctx, WorkingFiles.SCANNER_GROUPS_TRAFFIC)
    instances = (
        read_spark_tsv(ctx, WorkingFiles.SCANNER_IPS)
        .filter(F.col("id_source") != UNKNOWN_ID)
        .groupBy(*GROUP_KEY)
        .agg(F.array_sort(F.collect_list(F.struct(*INSTANCE_COLUMNS))).alias("instances"))
    )

    actors = (
        groups
        .join(instances, on=GROUP_KEY, how="left")
        .join(traffic, on=GROUP_KEY, how="left")
        .orderBy(group_order(), "id")
    )
    return [row.asDict(recursive=True) for row in actors.collect()]


def parse_sensor(row: dict[str, str]) -> DailySensor:
    return DailySensor(
        hostname=row["hostname"],
        ipv4=row["ipv4"],
        ipv6=row["ipv6"],
        creation=dt.datetime.fromisoformat(row["creation"]),
        region=row["region"],
        connections_total=int(row["connections_total"]),
        connections_full=int(row["connections_full"]),
        connections_half_open=int(row["connections_half_open"]),
    )


def parse_actor(row: dict[str, Any]) -> DailyActor:
    instances = [parse_instance(i) for i in row["instances"] or []]
    # ip_count ist redundant zu instances und wird nur geprüft, nicht übernommen (unknown hat keine instances).
    if row["id_source"] != UNKNOWN_ID and len(instances) != int(row["ip_count"]):
        raise ValueError(f"{row['id']}: ip_count passt nicht zu den IPs in scanner_ips.tsv")
    if row["connections_total"] is None:
        raise ValueError(f"{row['id']}: keine Zeile in scanner_groups_traffic.tsv")

    return DailyActor(
        id=row["id"],
        id_source=row["id_source"],
        editorial_suffix=row["editorial_suffix"] or None,
        editorial_type=row["editorial_type"] or None,
        isc_ids=json.loads(row["isc_ids"]),
        instances=instances,
        protocols=parse_protocols(row),
        traffic=parse_traffic(row),
    )


def parse_instance(row: dict[str, Any]) -> DailyScannerInstance:
    return DailyScannerInstance(
        ip=row["ip"],
        hostname=row["hostname"] or None,
        dns_status=row["dns_status"],
        fcrdns_valid=row["fcrdns_valid"] == "True",
        isc_id=row["isc_id"] or None,
    )


def parse_traffic(row: dict[str, Any]) -> DailyTraffic:
    """sensors_hit aus der JSON-Spalte scanned_ips; alle übrigen Felder sind Zähler und heißen wie die Spalten."""
    counts = {f.name: int(row[f.name]) for f in fields(DailyTraffic) if f.name != "sensors_hit"}
    return DailyTraffic(sensors_hit=json.loads(row["scanned_ips"]), **counts)


def parse_protocols(row: dict[str, Any]) -> dict[Protocol, ProtocolResult]:
    """Alle Protokolle; ohne Kontakt stehen beide Level auf 0 (in t2_group_sanners per fillna gesetzt)."""
    protocols = {}
    for protocol in Protocol:
        transport = TransportLevel(int(row[f"{protocol}_transport_level"]))
        application = APPLICATION_LEVELS[protocol](_number(row[f"{protocol}_application_level"]))
        protocols[protocol] = ProtocolResult.from_levels(protocol, transport, application)
    return protocols


def _number(value: str) -> int | float:
    number = float(value)
    return int(number) if number.is_integer() else number
