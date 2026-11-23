"""Aggregierte Datei, berechnet aus den Tagesdateien (siehe daily.py).

last_7d, last_31d und last_365d werden aus den Tagesdateien des Fensters berechnet. all wird fortlaufend
aus dem all-Fenster des vorherigen AggregatedResult und der neuen Tagesdatei fortgeschrieben;
dafür sind alle Felder so gewählt, dass sie sich aus Vorstand + neuem Tag ergeben
(Summe, Maximum, Vereinigung, Minimum/Maximum eines Datums, Zähler oder jüngster Stand).
Damit haben alle Fenster dieselbe Struktur.
"""

import datetime as dt
from dataclasses import dataclass
from typing import Literal

from .common import ActorId, ProtocolResult
from .daily import DailyTraffic
from .levels import Protocol

# Länge der festen Fenster in Tagen, jeweils einschließlich as_of (Felder von Windows außer all)
WINDOW_DAYS = {"last_7d": 7, "last_31d": 31, "last_365d": 365}
MAX_WINDOW_DAYS = max(WINDOW_DAYS.values())


@dataclass
class Coverage:
    """Zeigt, wie vollständig ein Fenster ist."""

    days_expected: int  # Anzahl der Tage im Fenster
    days_included: int  # Anzahl der Tage mit vorhandener Tagesdatei
    days_missing: list[dt.date]  # Tage ohne Tagesdatei


@dataclass
class WindowSensor:
    """Ein Sensor (Descriptor) im Zeitfenster; Schlüssel ist ipv4 + creation."""

    hostname: str
    ipv4: str
    ipv6: str
    creation: dt.datetime
    region: str
    connections_total: int  # Summe der Tageswerte
    connections_full: int  # Summe der Tageswerte
    connections_half_open: int  # Summe der Tageswerte


@dataclass
class WindowScannerInstance:
    """Eine Scanner-IP einer Gruppe im Zeitfenster; Schlüssel ist ip (innerhalb der Gruppe)."""

    ip: str
    hostname: str | None  # jüngster Stand
    dns_status: str  # jüngster Stand
    fcrdns_valid: bool  # jüngster Stand
    isc_id: str | None  # jüngster Stand
    first_seen: dt.date  # erster Tag im Fenster, an dem die IP in der Gruppe war
    last_seen: dt.date  # letzter Tag im Fenster, an dem die IP in der Gruppe war
    days_seen: int  # Anzahl der Tage im Fenster, an denen die IP in der Gruppe war


@dataclass
class WindowActor:
    """Eine Scanner-Gruppe im Zeitfenster; Schlüssel ist id_source + id."""

    id: ActorId
    id_source: Literal["editorial", "isc", "unknown"]
    editorial_suffix: str | None  # jüngster Stand
    editorial_type: str | None  # jüngster Stand
    isc_ids: list[str]  # Vereinigung über alle Tage
    first_seen: dt.date  # erster Tag im Fenster, an dem die Gruppe beobachtet wurde
    last_seen: dt.date  # letzter Tag im Fenster, an dem die Gruppe beobachtet wurde
    days_seen: int  # Anzahl der Tage im Fenster mit Beobachtung
    # Vereinigung der Tages-instances über ip, sortiert nach ip; leer bei "unknown" (wie in der Tagesdatei)
    instances: list[WindowScannerInstance]
    protocols: dict[Protocol, ProtocolResult]  # Maxima über alle Tage, Score daraus neu berechnet
    # sensors_hit vereinigt, connections_* summiert, max_conn_* als Maximum der Tageswerte
    # (*_day: höchster Wert an einem einzelnen Tag, *_1h: höchster Wert in einer Stunde)
    traffic: DailyTraffic


@dataclass
class Window:
    """Ergebnis eines Zeitfensters."""

    start: dt.date  # erster Tag des Fensters
    end: dt.date  # letzter Tag des Fensters, entspricht as_of
    coverage: Coverage
    sensors: list[WindowSensor]  # alle Sensoren aus den Tagesdateien des Fensters
    actors: list[WindowActor]  # im Fenster beobachtete Scanner-Gruppen


@dataclass
class Windows:
    last_7d: Window  # letzte 7 Tage einschließlich as_of
    last_31d: Window  # letzte 31 Tage einschließlich as_of
    last_365d: Window  # letzte 365 Tage einschließlich as_of
    all: Window  # gesamter Zeitraum seit der ersten Tagesdatei, fortlaufend fortgeschrieben


@dataclass
class AggregatedResult:
    """Stand aller Zeitfenster an einem Tag, berechnet aus den Tagesdateien."""

    schema_version: int  # Version dieser Datenstruktur
    as_of: dt.date  # letzter Tag, der in die Fenster einfließt
    generated_at: dt.datetime  # Zeitpunkt der Erzeugung dieser Datei (UTC)
    windows: Windows
