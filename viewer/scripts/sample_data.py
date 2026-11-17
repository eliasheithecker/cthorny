"""Baut aus einer Tagesdatei Beispiel-Aggregatdateien für die lokale Entwicklung.

Solange Schritt 6 (Aggregation) fehlt, gibt es nur eine echte Tagesdatei. Daraus werden
--days künstliche Stichtage bis zum Datum der Tagesdatei erzeugt, damit sich der Zeitstrahl
testen lässt. Die Werte sind NICHT echt:
- Jede Gruppe gilt an zufällig (deterministisch) gewählten Tagen als beobachtet.
- Jede IP einer Gruppe ist nur an einem Teil dieser Tage dabei (first_seen/last_seen/days_seen je IP).
- connections_* von Gruppen und Sensoren werden mit der Zahl der Tage multipliziert;
  die max_conn_*-Werte bleiben, weil jeder Tag dieselben Tageswerte hat.
- Einzelne Tage fehlen absichtlich.

Ablage wie in analyser/idee.md: <results_dir>/aggregated/YYYY-MM-DD.json
Struktur wie AggregatedResult in analyser/src/models/aggregated.py.

Aufruf: python3 scripts/sample_data.py <daily_result.json> <results_dir> [--days N]
"""

import argparse
import datetime as dt
import json
import zlib
from pathlib import Path

WINDOW_DAYS = {"last_7d": 7, "last_31d": 31, "last_365d": 365}
TRAFFIC_SUMS = ("connections_total", "connections_full", "connections_half_open")


def _hash(*parts: object) -> int:
    return zlib.crc32("/".join(map(str, parts)).encode())


def seen(actor_id: str, day: dt.date) -> bool:
    """Deterministisch: Gruppe an etwa 80 % der Tage beobachtet."""
    return _hash(actor_id, day) % 5 != 0


def instance_seen(actor_id: str, ip: str, day: dt.date) -> bool:
    """Deterministisch: IP an etwa 70 % der Tage ihrer Gruppe dabei."""
    return _hash(actor_id, ip, day) % 10 < 7


def instances_per_day(actor: dict, days: list[dt.date]) -> dict[str, list[dt.date]]:
    """IP => Tage, an denen sie in der Gruppe war; an jedem Gruppentag ist mindestens eine IP dabei."""
    result: dict[str, list[dt.date]] = {i["ip"]: [] for i in actor["instances"]}
    for day in days:
        ips = [ip for ip in result if instance_seen(actor["id"], ip, day)] or list(result)
        for ip in ips:
            result[ip].append(day)
    return result


def window_actor(actor: dict, days_seen: list[dt.date]) -> dict:
    per_ip = instances_per_day(actor, days_seen)
    instances = [
        {
            **inst,
            "first_seen": per_ip[inst["ip"]][0].isoformat(),
            "last_seen": per_ip[inst["ip"]][-1].isoformat(),
            "days_seen": len(per_ip[inst["ip"]]),
        }
        for inst in actor["instances"]
        if per_ip[inst["ip"]]
    ]

    traffic = dict(actor["traffic"])
    for key in TRAFFIC_SUMS:
        traffic[key] *= len(days_seen)

    return {
        "id": actor["id"],
        "id_source": actor["id_source"],
        "editorial_suffix": actor["editorial_suffix"],
        "editorial_type": actor["editorial_type"],
        "isc_ids": actor["isc_ids"],
        "first_seen": days_seen[0].isoformat(),
        "last_seen": days_seen[-1].isoformat(),
        "days_seen": len(days_seen),
        "instances": instances,
        "protocols": actor["protocols"],
        "traffic": traffic,
    }


def window(daily: dict, start: dt.date, end: dt.date, available: set[dt.date]) -> dict:
    days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    included = [d for d in days if d in available]

    actors = []
    for a in daily["actors"]:
        days_seen = [d for d in included if seen(a["id"], d)]
        if days_seen:
            actors.append(window_actor(a, days_seen))

    sensors = []
    for s in daily["sensors"]:
        sensor = dict(s)
        for key in TRAFFIC_SUMS:
            sensor[key] *= len(included)
        sensors.append(sensor)

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "coverage": {
            "days_expected": len(days),
            "days_included": len(included),
            "days_missing": [d.isoformat() for d in days if d not in available],
        },
        "sensors": sensors,
        "actors": actors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("daily")
    parser.add_argument("results_dir")
    parser.add_argument("--days", type=int, default=60)
    args = parser.parse_args()

    daily = json.loads(Path(args.daily).read_text())
    last = dt.date.fromisoformat(daily["date"])
    first = last - dt.timedelta(days=args.days - 1)
    # Einzelne Tage ohne Ergebnis, um Lücken im Zeitstrahl zu zeigen; der letzte Tag ist immer da
    available = {
        first + dt.timedelta(days=i)
        for i in range(args.days)
        if i % 11 != 5 or first + dt.timedelta(days=i) == last
    }

    out_dir = Path(args.results_dir) / "aggregated"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()

    for as_of in sorted(available):
        # Tage vor dem ersten Stichtag sind nicht in available und zählen damit als fehlend
        windows = {
            name: window(daily, as_of - dt.timedelta(days=n - 1), as_of, available)
            for name, n in WINDOW_DAYS.items()
        }
        windows["all"] = window(daily, first, as_of, available)

        result = {
            "schema_version": daily["schema_version"],
            "as_of": as_of.isoformat(),
            "generated_at": dt.datetime.combine(as_of + dt.timedelta(days=1), dt.time(3), dt.UTC).isoformat(),
            "windows": windows,
        }
        (out_dir / f"{as_of}.json").write_text(json.dumps(result, separators=(",", ":")))

    print(f"{out_dir}: {len(available)} Stichtage von {first} bis {last} (Beispieldaten, nicht echt)")


if __name__ == "__main__":
    main()
