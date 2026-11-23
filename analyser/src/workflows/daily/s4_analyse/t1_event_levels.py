import logging
from pathlib import Path

from utils import Context
from models.paths import WorkingFiles

import pandas as pd

from pyspark.sql import functions as F

log = logging.getLogger(__name__)


def event_levels(ctx: Context) -> None:
    output_file = ctx.workingPathOf(WorkingFiles.EVENT_LEVELS)
    if not ctx.force_reload and output_file.exists():
        log.info("Event levels already exist, skipping step")
        return
    Path(output_file.parent).mkdir(parents=True, exist_ok=True)
    log.debug("output_dir created: %s", output_file.parent)

    scanner_ips_validated = load_validated_scanner_ips(ctx)
    syn_sdf = read_syn_ack_events(ctx)
    ssh_events = obtain_ssh_events(ctx, scanner_ips_validated, syn_sdf)
    telnet_events = obtain_telnet_events(ctx, scanner_ips_validated, syn_sdf)
    smtp_events = obtain_smtp_events(ctx, scanner_ips_validated, syn_sdf)
    ldap_events = obtain_ldap_events(ctx, scanner_ips_validated, syn_sdf)

    # Combine all protocol events into one list:
    # ip | protocol | transport_level | application_level
    all_events = (
        to_common_schema(ssh_events, "ssh")
        .unionByName(to_common_schema(telnet_events, "telnet"))
        .unionByName(to_common_schema(smtp_events, "smtp"))
        .unionByName(to_common_schema(ldap_events, "ldap"))
    )

    all_events.toPandas().to_csv(
        str(output_file),
        sep="\t",
        index=False,
        header=True
    )
    log.info("Event levels saved to %s", output_file)


def to_common_schema(events_sdf, protocol: str):
    """Renames the protocol-specific level columns so all events share one schema."""
    return events_sdf.select(
        "ip",
        F.lit(protocol).alias("protocol"),
        F.col(f"{protocol}_transport_level").cast("int").alias("transport_level"),
        F.col(f"{protocol}_application_level").cast("int").alias("application_level"),
    )


def obtain_ssh_events(ctx: Context, scanner_ips_sdf: pd.DataFrame, syn_sdf : pd.DataFrame) -> pd.DataFrame:
    ssh_logs_sdf = ctx.spark.read.json(str(ctx.workingPathOf(WorkingFiles.HANDLER_LOGS_SSH)))

    # SYN events: transport level 1, no application interaction
    ssh_syn_events = (
        syn_sdf
        .filter(F.col("protocol") == "ssh")
        .join(
            scanner_ips_sdf.select("ip"),
            syn_sdf["client_ip"] == scanner_ips_sdf["ip"],
            "inner"
        )
        .select(
            F.col("client_ip").alias("ip"),
            F.lit(1).alias("ssh_transport_level"),
            F.lit(0).alias("ssh_application_level")
        )
    )
    
    # Full TCP connection (SSH logs): transport level 2
    ssh_full_events = (
        ssh_logs_sdf
        .join(
            scanner_ips_sdf.select("ip"),
            ssh_logs_sdf["client_ip"] == scanner_ips_sdf["ip"],
            "inner"
        )
        .withColumn("ssh_transport_level", F.lit(2))
        .withColumn(
            "ssh_application_level",
            F.when(
                F.expr("exists(messages, m -> m like '%sudo%')") |
                F.expr("exists(messages, m -> m like '%su%')")| 
                F.col("command_data").like("%sudo%") |
                F.col("command_data").like("%su%"),
                4
            )
            .when(F.col("command_attempted") == True, 3)
            .when(F.col("login_attempted") == True, 2)
            .when(
                (F.col("client_banner") != "") & (F.col("login_attempted") == False),
                1
            )
            .otherwise(0)
        )
        .select(
            F.col("client_ip").alias("ip"),
            "ssh_transport_level",
            "ssh_application_level"
        )
    )

    # combine events
    ssh_events = ssh_syn_events.unionByName(ssh_full_events)
    return ssh_events

        
def obtain_telnet_events(ctx: Context, scanner_ips_sdf: pd.DataFrame, syn_sdf : pd.DataFrame) -> pd.DataFrame:
    telnet_logs_sdf = ctx.spark.read.json(str(ctx.workingPathOf(WorkingFiles.HANDLER_LOGS_TELNET)))

    # SYN events: transport level 1, no application interaction
    telnet_syn_events = (
        syn_sdf
        .filter(F.col("protocol") == "telnet")
        .join(
            scanner_ips_sdf.select("ip"),
            syn_sdf["client_ip"] == scanner_ips_sdf["ip"],
            "inner"
        )
        .select(
            F.col("client_ip").alias("ip"),
            F.lit(1).alias("telnet_transport_level"),
            F.lit(0).alias("telnet_application_level") 
        )
    )

    # Full TCP connection (telnet logs): transport level 2
    telnet_full_events = (
        telnet_logs_sdf
        .join(
            scanner_ips_sdf.select("ip"),
            telnet_logs_sdf["client_ip"] == scanner_ips_sdf["ip"],
            "inner"
        )
        .withColumn("telnet_transport_level", F.lit(2))
        .withColumn(
            "telnet_application_level",
            F.when(
                F.expr("exists(messages, m -> m like '%sudo%')") |
                F.expr("exists(messages, m -> m like '%su%')"),
                3
            )
            .when(
                (F.length(F.col("username")) > 0) & 
                (F.length(F.col("username")) <= 10) & 
                (~F.col("username").rlike(r"\s")) &  # Kein Leerzeichen im User
                (F.length(F.col("password")) > 0) &
                (~F.col("password").rlike(r"\s")) &  # Kein Leerzeichen im PW
                (F.col("messages_count") > 2), 
                2
            )
            .when(
                (F.length(F.col("username")) > 0) & 
                (F.length(F.col("username")) <= 10) & 
                (~F.col("username").rlike(r"\s")) &  # Kein Leerzeichen im User
                (F.length(F.col("password")) > 0) &
                (~F.col("password").rlike(r"\s")),   # Kein Leerzeichen im PW
                1
            )
            .otherwise(0)
        )
        .select(
            F.col("client_ip").alias("ip"),
            "telnet_transport_level",
            "telnet_application_level"
        )
    )

   # combine events
    telnet_events = telnet_syn_events.unionByName(telnet_full_events)
    return telnet_events

def obtain_smtp_events(ctx: Context, scanner_ips_sdf: pd.DataFrame, syn_sdf : pd.DataFrame) -> pd.DataFrame:
    smtp_logs_sdf = ctx.spark.read.json(str(ctx.workingPathOf(WorkingFiles.HANDLER_LOGS_SMTP)))

    # Base handler logs
    smtp_handler_base = (
        smtp_logs_sdf
        .join(
            scanner_ips_sdf.select("ip"),
            smtp_logs_sdf.client_ip == scanner_ips_sdf.ip,
            "inner"
        )
    )

    # SMTP full interaction events
    smtp_full_events = (
        smtp_handler_base
        .withColumn(
            "smtp_transport_level",
            F.when(F.col("tls_used") == True, 4)
            .when(F.col("tls_tested") == True, 3)
            .otherwise(2)
        )
        .withColumn(
            "smtp_application_level",
            F.when(
                (F.expr("exists(commands, m -> m like '%AUTH%')")) |
                (F.expr("exists(commands, m -> m like '%auth%')")),
                4
            )
            .when(
                (F.length(F.col("sender")) > 0) &
                (F.size(F.col("recipients")) > 0) &
                (F.col("body_len") > 0),
                3 # mail sent tested -- could also just be checking for mail command
            )
            .when(
                (F.expr("exists(commands, m -> m like '%ehlo%')")) |
                (F.expr("exists(commands, m -> m like '%EHLO%')")) |
                (F.expr("exists(commands, m -> m like '%VRFY%')")) |
                (F.expr("exists(commands, m -> m like '%vrfy%')")) |
                (F.expr("exists(commands, m -> m like '%HELP%')")) |
                (F.expr("exists(commands, m -> m like '%help%')")),
                2  # capability grabbing
            )
            .when(
                (F.size(F.col("commands")) > 0),
                1
            )
            .otherwise(0)
        )
        .select(
            F.col("client_ip").alias("ip"),
            "smtp_transport_level",
            "smtp_application_level"
        )
    )

    # SYN events
    smtp_syn_events = (
        syn_sdf
        .filter(F.col("protocol") == "smtp")
        .join(
            scanner_ips_sdf.select("ip"),
            syn_sdf["client_ip"] == scanner_ips_sdf["ip"],
            "inner"
        )
        .select(
            F.col("client_ip").alias("ip"),
            F.lit(1).alias("smtp_transport_level"),
            F.lit(0).alias("smtp_application_level")
        )
    )

    #combine events
    smtp_events = smtp_syn_events.unionByName(smtp_full_events)

    return smtp_events

def obtain_ldap_events(ctx: Context, scanner_ips_sdf: pd.DataFrame, syn_sdf : pd.DataFrame) -> pd.DataFrame:
    ldap_logs_sdf = ctx.spark.read.json(str(ctx.workingPathOf(WorkingFiles.HANDLER_LOGS_LDAP)))

    # Base handler logs (only scanner IPs)
    ldap_handler_base = (
        ldap_logs_sdf
        .join(
            scanner_ips_sdf.select("ip"),
            ldap_logs_sdf.client_ip == scanner_ips_sdf.ip,
            "inner"
        )
    )

    # ldap full interaction events
    ldap_full_events = (
        ldap_handler_base
        .withColumn(
            "ldap_transport_level",
            F.when(F.col("tls_version") != "", 4)
            .when(F.col("tls") == True, 3)
            .otherwise(2)
        )
        .withColumn(
            "ldap_application_level",
            F.when(
                (F.col("auth_attempted") == True) &
                (F.col("login_dn") != "") &
                (F.col("password") != ""),
                4  # bind with credentials attempted
            )
            .when(
                (F.col("search_attempted") == True),
                3 # search attempted
            )
            .when(
                (F.col("auth_attempted") == True),
                2 # anonymous bind attempted
            )
            .when(
                (F.col("num_messages") > 0),
                1 # command attempted
            )
            .otherwise(0)
        )
        .select(
            F.col("client_ip").alias("ip"),
            "ldap_transport_level",
            "ldap_application_level"
        )
    )

    # SYN events
    ldap_syn_events = (
        syn_sdf
        .filter(F.col("protocol") == "ldap")
        .join(
            scanner_ips_sdf.select("ip"),
            syn_sdf["client_ip"] == scanner_ips_sdf["ip"],
            "inner"
        )
        .select(
            F.col("client_ip").alias("ip"),
            F.lit(1).alias("ldap_transport_level"),
            F.lit(0).alias("ldap_application_level")
        )
    )

    # combine events
    ldap_events = ldap_syn_events.unionByName(ldap_full_events)
    return ldap_events

def load_validated_scanner_ips(ctx: Context) -> pd.DataFrame:
    scanner_ips_sdf = (
        ctx.spark.read
        .option("header", "true")
        .option("delimiter", "\t")
        .csv(str(ctx.workingPathOf(WorkingFiles.ALL_SCANNER_JOINED_VALIDATED)))
    )

    scanner_ips_sdf = scanner_ips_sdf.select(
        "ip",
        "editorial_id",
        "isc_id",
        "fcrdns_valid"
    ).distinct()

    scanner_ips_validated = scanner_ips_sdf.filter(
        ((scanner_ips_sdf["editorial_id"].isNotNull()) | (scanner_ips_sdf["isc_id"].isNotNull()))
    )

    return scanner_ips_validated

def read_syn_ack_events(ctx: Context) -> pd.DataFrame:
    syn_sdf = (
        ctx.spark.read
        .option("delimiter", "\t")
        .csv(str(ctx.workingPathOf(WorkingFiles.HALF_OPEN_EVENTS)))
        .toDF("timestamp", "client_ip", "client_port", "sensor_ip", "sensor_port")
    )
    
    syn_sdf = syn_sdf.withColumn(
        "protocol",
        F.when(F.col("sensor_port") == 22, "ssh")
        .when(F.col("sensor_port") == 25, "smtp")
        .when(F.col("sensor_port") == 23, "telnet")
        .when(F.col("sensor_port") == 389, "ldap")
    )
    
    return syn_sdf