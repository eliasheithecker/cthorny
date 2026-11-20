from utils import Context, cleanup_working_dir


def cleanup(ctx: Context) -> None:
    """Löscht das Arbeitsverzeichnis des Tages; abschaltbar über utils.working_dir.SKIP_CLEANUP."""
    cleanup_working_dir(ctx)
