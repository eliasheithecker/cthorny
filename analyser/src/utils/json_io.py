import datetime as dt
import json
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def to_jsonable(obj: Any) -> Any:
    """Dataclasses rekursiv in JSON-Typen umwandeln; Enums als Wert, Daten als ISO 8601."""
    if is_dataclass(obj):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, Enum):
        value = obj.value
        return int(value) if isinstance(value, float) and value.is_integer() else value
    if isinstance(obj, dict):
        return {to_jsonable(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (dt.date, dt.datetime)):
        return obj.isoformat()
    return obj


def write_json(obj: Any, path: Path) -> None:
    """Schreibt obj (auch Dataclasses) als JSON; erst in eine .part-Datei, damit ein Abbruch keine halbe Datei hinterlässt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    part_file = path.with_name(path.name + ".part")
    with part_file.open("w", encoding="utf-8") as f:
        json.dump(to_jsonable(obj), f, ensure_ascii=False, indent=2)
    part_file.replace(path)


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)
