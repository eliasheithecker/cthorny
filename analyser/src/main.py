import argparse
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from workflows.daily import daily_workflow
from workflows.aggregate import aggregate_workflow
from utils import Context, create_spark, setup_logging

log = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nächtliche Auswertung der Thorny-Sensordaten"
    )
    default = Path.cwd() / "tmp"
    parser.add_argument(
        "--working-tmp-dir",
        type=Path,
        default=default,
        help="Temporäres Arbeitsverzeichnis (Standard: aktuelles_Verzeichnis/tmp)",
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=datetime.now(UTC).date() - timedelta(days=1),
        help="Auszuwertender UTC-Tag als YYYY-MM-DD (Standard: gestern in UTC)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Log-Level DEBUG statt INFO",
    )
    parser.add_argument(
        "--force-reload",
        action="store_true",
        help="Zwischenergebnisse ignorieren und neu erzeugen",
    )
    parser.add_argument(
        "--only",
        choices=["daily", "aggregate"],
        default=None,
        help="Nur den daily- oder nur den aggregate-Workflow ausführen (Standard: beide)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    setup_logging(debug=args.debug)

    base_dir: Path = args.working_tmp_dir.resolve()
    if not base_dir.is_dir():
        raise SystemExit(f"working-tmp-dir existiert nicht: {base_dir}")
    # je Tag ein eigenes Arbeitsverzeichnis; existiert es schon, werden die Daten weiterverwendet
    working_dir = base_dir / args.date.isoformat()
    working_dir.mkdir(exist_ok=True)

    log.info("Working dir: %s", working_dir)
    log.debug("Argumente: %s", args)
    
    log.info(" ----  Initalisiere Spark")
    spark = create_spark(debug=args.debug)
    log.info(" ---- abgeschlossen.")
    try:
        ctx = Context(working_dir, spark, force_reload=args.force_reload, date_of_data=args.date)
        if args.only in (None, "daily"):
            daily_workflow(ctx)
        else:
            log.info("--only %s: daily workflow übersprungen", args.only)
        if args.only in (None, "aggregate"):
            aggregate_workflow(ctx)
        else:
            log.info("--only %s: aggregate workflow übersprungen", args.only)
    finally:
        spark.stop()
        log.debug("Spark-Session gestoppt")
        
    log.info(" ---- Fertig. Alle Schritte und Workflows abgeschlossen. ---- ")


if __name__ == "__main__":
    main()
