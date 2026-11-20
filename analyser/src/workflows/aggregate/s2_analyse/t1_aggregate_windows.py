"""
Führt Tagesdateien (DailyResult als JSON-dict) zu den Zeitfenstern eines AggregatedResult zusammen.

Reines Python auf dicts: Jede Tagesdatei wird genau einmal gelesen, in "Fensterform" gebracht
(first_seen = last_seen = Tag, days_seen = 1) und in alle Fenster gemischt, die den Tag enthalten.
Dieselbe Merge-Logik übernimmt auch das all-Fenster des Vortags-Aggregats (Fortschreiben).
Die Zusammenführungsregeln stehen in models/aggregated.py.
"""

import datetime as dt
import logging
from dataclasses import fields
from pathlib import Path
from typing import Any

from models import (
    APPLICATION_LEVELS,
    WINDOW_DAYS,
    Coverage,
    DailyTraffic,
    Protocol,
    ProtocolResult,
    TransportLevel,
    Window,
    WindowActor,
    WindowScannerInstance,
    Windows,
    WindowSensor,
)
from utils import group_sort_key, read_json

log = logging.getLogger(__name__)

CONNECTION_SUMS = ("connections_total", "connections_full", "connections_half_open")
TRAFFIC_MAXES = tuple(f.name for f in fields(DailyTraffic) if f.name.startswith("max_"))
SENSOR_LATEST = ("hostname", "ipv6", "region")
ACTOR_LATEST = ("editorial_suffix", "editorial_type")
INSTANCE_LATEST = ("hostname", "dns_status", "fcrdns_valid", "isc_id")

Entry = dict[str, Any]


class WindowAccumulator:
    """Sammelt Sensoren und Akteure eines Fensters [start, end]."""

    def __init__(self, start: dt.date, end: dt.date) -> None:
        self.start = start
        self.end = end
        self.days_included = 0
        self.days_missing: list[dt.date] = []
        self.sensors: dict[tuple[str, str], Entry] = {}  # (ipv4, creation)
        self.actors: dict[tuple[str, str], Entry] = {}  # (id_source, id)

    def add_day(self, sensors: list[Entry], actors: list[Entry]) -> None:
        self.days_included += 1
        self.merge(sensors, actors)

    def add_missing_day(self, day: dt.date) -> None:
        self.days_missing.append(day)

    def merge(self, sensors: list[Entry], actors: list[Entry]) -> None:
        """Sensoren und Akteure in Fensterform einmischen; die Eingaben werden nicht verändert."""
        for sensor in sensors:
            self._merge_sensor(sensor)
        for actor in actors:
            self._merge_actor(actor)

    def _merge_sensor(self, s: Entry) -> None:
        key = (s["ipv4"], s["creation"])
        acc = self.sensors.get(key)
        if acc is None:
            self.sensors[key] = dict(s)
            return
        for k in CONNECTION_SUMS:
            acc[k] += s[k]
        # Tage werden aufsteigend verarbeitet, der zuletzt gemischte Wert ist der jüngste
        for k in SENSOR_LATEST:
            acc[k] = s[k]

    def _merge_actor(self, a: Entry) -> None:
        key = (a["id_source"], a["id"])
        acc = self.actors.get(key)
        if acc is None:
            acc = self.actors[key] = {
                "id": a["id"],
                "id_source": a["id_source"],
                **{k: a[k] for k in ACTOR_LATEST},
                "isc_ids": set(),
                "first_seen": a["first_seen"],
                "last_seen": a["last_seen"],
                "days_seen": 0,
                "instances": {},
                "protocols": {},
                "traffic": {"sensors_hit": set(), **{k: 0 for k in (*CONNECTION_SUMS, *TRAFFIC_MAXES)}},
            }
        if a["last_seen"] >= acc["last_seen"]:
            for k in ACTOR_LATEST:
                acc[k] = a[k]
        acc["isc_ids"].update(a["isc_ids"])
        acc["first_seen"] = min(acc["first_seen"], a["first_seen"])
        acc["last_seen"] = max(acc["last_seen"], a["last_seen"])
        acc["days_seen"] += a["days_seen"]

        instances = acc["instances"]
        for inst in a["instances"]:
            cur = instances.get(inst["ip"])
            if cur is None:
                instances[inst["ip"]] = dict(inst)
                continue
            if inst["last_seen"] >= cur["last_seen"]:
                for k in INSTANCE_LATEST:
                    cur[k] = inst[k]
            cur["first_seen"] = min(cur["first_seen"], inst["first_seen"])
            cur["last_seen"] = max(cur["last_seen"], inst["last_seen"])
            cur["days_seen"] += inst["days_seen"]

        protocols = acc["protocols"]
        for proto, result in a["protocols"].items():
            transport, application = result["max_transport_level"], result["max_application_level"]
            cur = protocols.get(proto)
            if cur is None:
                protocols[proto] = [transport, application]
            else:
                cur[0] = max(cur[0], transport)
                cur[1] = max(cur[1], application)

        traffic, incoming = acc["traffic"], a["traffic"]
        traffic["sensors_hit"].update(incoming["sensors_hit"])
        for k in CONNECTION_SUMS:
            traffic[k] += incoming[k]
        for k in TRAFFIC_MAXES:
            traffic[k] = max(traffic[k], incoming[k])

    def to_window(self) -> Window:
        return Window(
            start=self.start,
            end=self.end,
            coverage=Coverage(
                days_expected=(self.end - self.start).days + 1,
                days_included=self.days_included,
                days_missing=sorted(self.days_missing),
            ),
            sensors=[_to_sensor(self.sensors[k]) for k in sorted(self.sensors)],
            actors=[_to_actor(self.actors[k]) for k in sorted(self.actors, key=lambda k: group_sort_key(*k))],
        )


def _to_sensor(s: Entry) -> WindowSensor:
    return WindowSensor(
        hostname=s["hostname"],
        ipv4=s["ipv4"],
        ipv6=s["ipv6"],
        creation=dt.datetime.fromisoformat(s["creation"]),
        region=s["region"],
        **{k: s[k] for k in CONNECTION_SUMS},
    )


def _to_actor(a: Entry) -> WindowActor:
    return WindowActor(
        id=a["id"],
        id_source=a["id_source"],
        editorial_suffix=a["editorial_suffix"],
        editorial_type=a["editorial_type"],
        isc_ids=sorted(a["isc_ids"]),
        first_seen=a["first_seen"],
        last_seen=a["last_seen"],
        days_seen=a["days_seen"],
        instances=[_to_instance(a["instances"][ip]) for ip in sorted(a["instances"])],
        protocols={
            proto: ProtocolResult.from_levels(
                proto,
                TransportLevel(a["protocols"][proto][0]),
                APPLICATION_LEVELS[proto](a["protocols"][proto][1]),
            )
            for proto in Protocol
            if proto in a["protocols"]
        },
        traffic=DailyTraffic(
            sensors_hit=sorted(a["traffic"]["sensors_hit"]),
            **{k: a["traffic"][k] for k in (*CONNECTION_SUMS, *TRAFFIC_MAXES)},
        ),
    )


def _to_instance(i: Entry) -> WindowScannerInstance:
    return WindowScannerInstance(
        ip=i["ip"],
        hostname=i["hostname"],
        dns_status=i["dns_status"],
        fcrdns_valid=i["fcrdns_valid"],
        isc_id=i["isc_id"],
        first_seen=i["first_seen"],
        last_seen=i["last_seen"],
        days_seen=i["days_seen"],
    )


def daily_to_window_form(day: dt.date, daily: Entry) -> tuple[list[Entry], list[Entry]]:
    """Tagesdatei in Fensterform bringen; ändert das (frisch gelesene) dict direkt, statt es zu kopieren."""
    for actor in daily["actors"]:
        actor.update(first_seen=day, last_seen=day, days_seen=1)
        for inst in actor["instances"]:
            inst.update(first_seen=day, last_seen=day, days_seen=1)
    return daily["sensors"], daily["actors"]


def window_to_window_form(window: Entry) -> tuple[list[Entry], list[Entry]]:
    """Fenster aus einem gelesenen AggregatedResult: Datumsangaben wieder in date umwandeln."""
    for actor in window["actors"]:
        _parse_seen(actor)
        for inst in actor["instances"]:
            _parse_seen(inst)
    return window["sensors"], window["actors"]


def _parse_seen(entry: Entry) -> None:
    entry["first_seen"] = dt.date.fromisoformat(entry["first_seen"])
    entry["last_seen"] = dt.date.fromisoformat(entry["last_seen"])


def aggregate_windows(as_of: dt.date, daily_files: dict[dt.date, Path], previous: Entry | None) -> Windows:
    """
    Berechnet alle Fenster für as_of.

    daily_files: vorhandene Tagesdateien (Tag -> Pfad), höchstens MAX_WINDOW_DAYS Tage bis as_of
    previous:    gelesenes AggregatedResult des Vortags oder None; dessen all-Fenster wird fortgeschrieben,
                 ohne es wird all aus daily_files neu aufgebaut
    """
    fixed = {
        name: WindowAccumulator(as_of - dt.timedelta(days=days - 1), as_of)
        for name, days in WINDOW_DAYS.items()
    }

    if previous is not None:
        prev_all = previous["windows"]["all"]
        prev_end = dt.date.fromisoformat(prev_all["end"])
        if prev_end >= as_of:
            raise ValueError(f"Vorheriges Aggregat reicht bis {prev_end}, kann nicht bis {as_of} fortgeschrieben werden")
        all_acc = WindowAccumulator(dt.date.fromisoformat(prev_all["start"]), as_of)
        all_acc.days_included = prev_all["coverage"]["days_included"]
        all_acc.days_missing = [dt.date.fromisoformat(d) for d in prev_all["coverage"]["days_missing"]]
        all_acc.merge(*window_to_window_form(prev_all))
        all_from = prev_end + dt.timedelta(days=1)
        log.info("all: schreibe Aggregat bis %s fort (Start %s)", prev_end, all_acc.start)
    else:
        if not daily_files:
            raise ValueError(f"Weder Tagesdateien noch vorheriges Aggregat für {as_of}")
        all_from = min(daily_files)
        all_acc = WindowAccumulator(all_from, as_of)
        log.warning("all: kein vorheriges Aggregat, baue aus %d Tagesdateien ab %s neu auf", len(daily_files), all_from)

    first_day = min(all_from, *(acc.start for acc in fixed.values()))
    day = first_day
    while day <= as_of:
        targets = [acc for acc in fixed.values() if acc.start <= day]
        if day >= all_from:
            targets.append(all_acc)
        if day in daily_files:
            daily = read_json(daily_files[day])
            if daily["date"] != day.isoformat():
                raise ValueError(f"{daily_files[day]} enthält den Tag {daily['date']}, erwartet {day}")
            sensors, actors = daily_to_window_form(day, daily)
            for acc in targets:
                acc.add_day(sensors, actors)
        else:
            for acc in targets:
                acc.add_missing_day(day)
        day += dt.timedelta(days=1)

    for name, acc in [*fixed.items(), ("all", all_acc)]:
        log.info(
            "%s: %s bis %s, %d/%d Tage, %d Akteure, %d Sensoren",
            name, acc.start, acc.end, acc.days_included, (acc.end - acc.start).days + 1,
            len(acc.actors), len(acc.sensors),
        )
    return Windows(
        last_7d=fixed["last_7d"].to_window(),
        last_31d=fixed["last_31d"].to_window(),
        last_365d=fixed["last_365d"].to_window(),
        all=all_acc.to_window(),
    )
