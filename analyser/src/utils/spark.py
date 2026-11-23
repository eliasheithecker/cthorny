"""Eine Spark-Session für den gesamten Lauf."""

from pyspark.sql import SparkSession


def create_spark(debug: bool = False) -> SparkSession:
    """Startet die lokale Spark-Session; wird in main einmal erzeugt und am Ende gestoppt."""
    spark = (
        SparkSession.builder
        .appName("thorny-analyser")
        .master("local[*]")
        .config("spark.sql.session.timeZone", "UTC")  # UTC-Tage, siehe idee.md
        .config("spark.driver.memory", "8g")          # lokal: Treiber = gesamter Prozess
        .config("spark.driver.bindAddress", "127.0.0.1")  # nicht über Hostname auflösen (bricht nach Netzwechsel/VPN)
        .config("spark.driver.host", "127.0.0.1")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("INFO" if debug else "WARN")
    return spark
