import logging
import shutil

from utils import Context

log = logging.getLogger(__name__)

# Zum Testen: True = Working dir nicht löschen, damit Zwischenergebnisse beim nächsten Lauf weiterverwendet werden
SKIP_CLEANUP = True


def cleanup(ctx: Context) -> None:
    """Löscht das Arbeitsverzeichnis des Tages (ctx.root_path, also <working-tmp-dir>/<YYYY-MM-DD>) komplett.

    Danach sind alle Zwischenergebnisse weg; ein erneuter Lauf für den Tag beginnt wieder beim Download.
    """
    working_dir = ctx.root_path.resolve()
    if SKIP_CLEANUP:
        log.info("SKIP_CLEANUP gesetzt, Working dir %s bleibt erhalten", working_dir)
        return
    if not working_dir.exists():
        log.info("Working dir %s existiert nicht, nichts aufzuräumen", working_dir)
        return

    # Schutz vor einem falsch gesetzten root_path: nur das Tagesverzeichnis aus main.py wird gelöscht
    if working_dir.name != ctx.date_of_data.isoformat() or not working_dir.is_dir():
        raise RuntimeError(
            f"Working dir {working_dir} ist kein Tagesverzeichnis für {ctx.date_of_data.isoformat()}, lösche nicht"
        )

    log.info("Lösche Working dir %s", working_dir)
    shutil.rmtree(working_dir)
    log.info("Working dir gelöscht")
