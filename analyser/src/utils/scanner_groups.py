"""Gemeinsame Definitionen der Scanner-Gruppen (s4_analyse, s5_convert)."""

from pyspark.sql import Column
from pyspark.sql import functions as F

UNKNOWN_ID = "unknown"
# Eine Gruppe wird immer über Quelle + ID identifiziert, damit gleichnamige
# editorial- und isc-IDs nicht zusammenfließen.
GROUP_KEY = ["id_source", "id"]


def group_order() -> Column:
    """Sortierung der Gruppen: editorial -> isc -> unknown."""
    return (
        F.when(F.col("id_source") == "editorial", 0)
        .when(F.col("id_source") == "isc", 1)
        .otherwise(2)
    )
