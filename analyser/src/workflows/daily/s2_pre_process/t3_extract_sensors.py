import logging

from pyspark.sql.functions import input_file_name, regexp_extract
from pathlib import Path

from utils import Context
from models.paths import WorkingFiles

log = logging.getLogger(__name__)

def extract_sensors(ctx: Context) -> None:
    
    sensors_dir = ctx.workingPathOf(WorkingFiles.SENSORS_DIR)
    if not ctx.force_reload and sensors_dir.exists() and any(sensors_dir.iterdir()):
        log.info("Sensor-Daten bereits extrahiert, überspringe Schritt")
        return
    
    raw_descriptors_dir = ctx.workingPathOf(WorkingFiles.RAW_DESCRIPTORS_DIR)
    
    spark_df = (
        ctx.spark.read
            .option("recursiveFileLookup", "true")
            .json(str(raw_descriptors_dir))
            .withColumn("source_path", input_file_name())
            .withColumn(
                "ip_from_dir",
                regexp_extract("source_path", r"([0-9]+-[0-9]+-[0-9]+-[0-9]+)", 1)
            )
    )

    df = spark_df.toPandas()

    sensors_dir.mkdir(parents=True, exist_ok=True)

    descriptors_file = ctx.workingPathOf(WorkingFiles.SENSORS_DESCRIPTORS)
    df.to_csv(str(descriptors_file), sep=',', index=False, header=False)
    log.info("Extrahierte Sensor-Daten gespeichert in %s", descriptors_file)

    ips_file = ctx.workingPathOf(WorkingFiles.SENSORS_IPs)
    ips = df[['ipv4', 'ipv6']].drop_duplicates()
    ips.to_csv(str(ips_file), sep=',', index=False)
    log.info("Extrahierte Sensor-IPs gespeichert in %s", ips_file)
    
    ipv4_file = ctx.workingPathOf(WorkingFiles.SENSORS_IPsV4)
    ips['ipv4'].to_csv(str(ipv4_file), sep=',', index=False, header=None)
    log.info("Extrahierte Sensor-IPv4 gespeichert in %s", ipv4_file)
