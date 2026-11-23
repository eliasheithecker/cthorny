import logging
import subprocess

from pathlib import Path

from utils import Context
from models.paths import WorkingFiles

log = logging.getLogger(__name__)

# SYN ohne ACK oder ACK ohne SYN, kein RST, ohne Nutzdaten
TSHARK_FILTER = (
    "tcp && ({dst_filter}) && "
    "((tcp.flags.syn==1 && tcp.flags.ack==0) || (tcp.flags.ack==1 && tcp.flags.syn==0)) && "
    "tcp.flags.reset==0 && "
    "tcp.len==0"
)
TSHARK_FIELDS = [
    "frame.time_epoch",
    "ip.src",
    "ip.dst",
    "tcp.srcport",
    "tcp.dstport",
    "tcp.flags",
]

def filter_pacap(ctx: Context) -> None:
    """Zieht per tshark die SYN- und ACK-Pakete an die Sensoren aus der zusammengeführten PCAP.

    Ergebnis ist eine TSV ohne Header mit den Spalten aus TSHARK_FIELDS.
    """
    output_file = ctx.workingPathOf(WorkingFiles.TCP_HANDSHAKE_MIN)
    if not ctx.force_reload and output_file.exists():
        log.info("TCP Handshake Filtered PCAP already exists, skipping step")
        return
    log.debug("output_file will be: %s", output_file)

    output_dir = ctx.workingPathOf(WorkingFiles.SYN_ACK_EVENTS_DIR)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    log.debug("ouput_dir created: %s", output_file.parent)

    # IPs zu "ip.dst==ip1 || ip.dst==ip2 || ..." verbinden; ignoriert \r und Leerzeilen
    ips = read_sensor_ips(ctx)
    dst_filter = " || ".join(f"ip.dst=={ip}" for ip in ips)
    log.debug("dst_filter: %s", dst_filter)

    pcap_file = ctx.workingPathOf(WorkingFiles.PCAPS_FILE)
    command = [
        "tshark",
        "-r", str(pcap_file),
        "-n", "-l",
        "-o", "tcp.desegment_tcp_streams:false",
        "-o", "tcp.analyze_sequence_numbers:false",
        "-Y", TSHARK_FILTER.format(dst_filter=dst_filter),
        "-T", "fields",
    ]
    for field in TSHARK_FIELDS:
        command += ["-e", field]

    # erst in eine .part-Datei schreiben, damit ein abgebrochener Lauf nicht als fertig gilt
    part_file = output_file.with_name(output_file.name + ".part")
    with open(part_file, "wb") as out:
        subprocess.run(command, stdout=out, check=True)
    part_file.replace(output_file)
    log.info("SYN/ACK-Pakete von %d Sensoren gespeichert in %s", len(ips), output_file)


def read_sensor_ips(ctx: Context) -> list[str]:
    """Liest die Sensor-IPv4 aus ips_v4.csv: erste Spalte, ohne \\r und Leerzeilen."""
    ips_file = ctx.workingPathOf(WorkingFiles.SENSORS_IPsV4)
    ips = [
        line.split()[0]
        for line in ips_file.read_text().replace("\r", "").splitlines()
        if line.strip()
    ]
    if len(ips) == 0:
        log.error("Keine Sensor-IPs gefunden")
        raise SystemExit(f"Keine Sensor-IPs in {ips_file}")
    return ips
