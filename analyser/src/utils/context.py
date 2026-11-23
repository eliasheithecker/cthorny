from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Date

from pyspark.sql import SparkSession

from models.paths import WorkingFiles


@dataclass(frozen=True)
class Context:
    root_path: Path  # Wurzel des Arbeitsverzeichnisses, z. B. aus --working-tmp-dir
    spark: SparkSession  # eine Session für den gesamten Lauf, siehe utils.spark
    date_of_data: Date
    force_reload: bool = False # Wenn True, werden Zwischenergebnisse ignoriert und neu erzeugt
    analyse_unkown: bool = False # Wenn True, werden unbekannte Scanner analysiert, sonst nicht

    def workingPathOf(self, file: WorkingFiles) -> Path:
        """Vollständiger Pfad zu einem Eintrag aus WorkingFiles."""
        return self.root_path / file
