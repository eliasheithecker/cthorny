"""Einheitliches Logging für den nächtlichen Lauf.

Nutzung in den Modulen:
    log = logging.getLogger(__name__)
"""

import logging
import time

FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
DATEFMT = "%Y-%m-%dT%H:%M:%SZ"


def setup_logging(debug: bool = False) -> None:
    """Richtet das Root-Logging ein: INFO, mit debug=True DEBUG; Zeiten in UTC."""
    logging.Formatter.converter = time.gmtime
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format=FORMAT,
        datefmt=DATEFMT,
    )
    # PySpark-Bridge ist auf DEBUG sehr gesprächig
    logging.getLogger("py4j").setLevel(logging.WARNING)
