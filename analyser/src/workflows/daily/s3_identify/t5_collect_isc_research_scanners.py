import csv
import logging
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from utils import Context
from models.paths import WorkingFiles

log = logging.getLogger(__name__)

# Liefert alle Research-Scanner, deren lastseen im Zeitraum [start, end] liegt.
# Start = Ende = Tag der Daten -> alle an diesem Tag gesehenen Research-Scanner.
ISC_RESEARCH_URL = "https://isc.sans.edu/api/threatcategory/research/{start}/{end}"
USER_AGENT = "thorny-analyser"
TIMEOUT_SECONDS = 60

FIELDS = ["ip", "first_seen", "last_seen", "isc_id"]
# XML-Tag -> Spalte in der TSV
XML_TO_FIELD = {
    "ipv4": "ip",
    "added": "first_seen",
    "lastseen": "last_seen",
    "type": "isc_id",
}


def _fetch_xml(day: str) -> bytes:
    url = ISC_RESEARCH_URL.format(start=day, end=day)
    log.debug("Fetching ISC research scanners from %s", url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


def _parse_research(xml_data: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(xml_data)
    rows = []
    for entry in root.iter("research"):
        row = {
            field: (entry.findtext(tag) or "").strip()
            for tag, field in XML_TO_FIELD.items()
        }
        if not row["ip"]:
            log.warning("ISC research entry without ipv4 skipped: %s", ET.tostring(entry))
            continue
        rows.append(row)
    return rows


def collect_isc_research_scanners(ctx: Context) -> None:
    output_file = ctx.workingPathOf(WorkingFiles.ISC_RESEARCH_SCANNER)

    if not ctx.force_reload and output_file.exists():
        log.info("ISC Research scanner list already created, skipping step")
        return

    Path(output_file.parent).mkdir(parents=True, exist_ok=True)
    log.debug("ouput_dir created: %s", output_file.parent)

    day = ctx.date_of_data.isoformat()
    rows = _parse_research(_fetch_xml(day))

    # Erst in eine temporäre Datei schreiben, damit ein abgebrochener Lauf
    # keine halbe Datei hinterlässt, die beim nächsten Lauf übersprungen würde.
    tmp_file = output_file.with_suffix(output_file.suffix + ".tmp")
    with open(tmp_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    tmp_file.replace(output_file)

    log.info("%d ISC research scanners for %s saved to %s", len(rows), day, output_file)
