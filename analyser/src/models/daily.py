"""
Tagesdatei, erzeugt aus den Ausgaben von s4_analyse:
scanner_groups.tsv + scanner_ips.tsv (t2), scanner_groups_traffic.tsv (t3), sensor_metadata.tsv (t4).
"""

import datetime as dt
from dataclasses import dataclass
from typing import Literal

from .common import ActorId, ProtocolResult
from .levels import Protocol


@dataclass
class DailySensor:
    """Ein Sensor (Descriptor) mit den Verbindungen, die an ihm ankamen; Zählweise wie DailyTraffic."""

    hostname: str
    ipv4: str  # öffentliche IP; kann bei Spot-Instanzen mehrere Descriptoren haben
    ipv6: str
    creation: dt.datetime  # Startzeit; gilt bis zum nächsten Descriptor derselben IP
    region: str
    connections_total: int  # alle Verbindungsversuche
    connections_full: int  # davon mit abgeschlossenem Handshake
    connections_half_open: int  # davon ohne ACK innerhalb des Timeouts


@dataclass
class DailyTraffic:
    """
    Verbindungs-Kennzahlen einer Scanner-Gruppe; eine Verbindung ist ein SYN ohne ACK.
    max_conn_per_sensor*: alle IPs der Gruppe zusammen;
    max_conn_per_scanner_instance_per_sensor*: eine einzelne IP der Gruppe.
    """

    sensors_hit: list[str]  # Sensor-IPs, die die Gruppe kontaktiert hat
    connections_total: int  # alle Verbindungsversuche
    connections_full: int  # davon mit abgeschlossenem Handshake
    connections_half_open: int  # davon ohne ACK innerhalb des Timeouts
    max_conn_per_sensor_port_day: int  # höchste Zahl an Verbindungen auf ein Paar aus Sensor und Port
    max_conn_per_sensor_port_1h: int  # wie oben, innerhalb eines gleitenden 60-Minuten-Fensters
    max_conn_per_sensor_day: int  # höchste Zahl an Verbindungen auf einen Sensor
    max_conn_per_sensor_1h: int  # wie oben, innerhalb eines gleitenden 60-Minuten-Fensters
    # höchste Zahl an Verbindungen einer einzelnen IP der Gruppe auf ein Paar aus Sensor und Port
    max_conn_per_scanner_instance_per_sensor_port_day: int
    max_conn_per_scanner_instance_per_sensor_port_1h: int  # wie oben, innerhalb eines gleitenden 60-Minuten-Fensters
    max_conn_per_scanner_instance_per_sensor_day: int  # höchste Zahl an Verbindungen einer einzelnen IP der Gruppe auf einen Sensor
    max_conn_per_scanner_instance_per_sensor_1h: int  # wie oben, innerhalb eines gleitenden 60-Minuten-Fensters


@dataclass
class DailyScannerInstance:
    """Eine einzelne Scanner-IP einer Gruppe mit ihren eigenen DNS-/ISC-Werten."""

    ip: str
    hostname: str | None  # PTR-Hostname; None ohne PTR-Record
    dns_status: str  # Status der PTR-Abfrage, z. B. NOERROR, NXDOMAIN
    fcrdns_valid: bool  # Hostname löst wieder auf diese IP auf
    isc_id: str | None  # ISC-Name dieser IP, falls gelistet


@dataclass
class DailyActor:
    """Eine Scanner-Gruppe an diesem Tag."""

    id: ActorId  # editorial_id, isc_id oder "unknown"
    id_source: Literal["editorial", "isc", "unknown"]  # Herkunft der id; editorial gewinnt vor isc
    editorial_suffix: str | None  # PTR-Suffix aus scanners.csv; None bei ISC-Gruppen
    editorial_type: str | None  # Akteurstyp aus scanners.csv, z. B. Academic; None bei ISC-Gruppen
    isc_ids: list[str]  # ISC-Namen, unter denen IPs der Gruppe gelistet sind
    instances: list[DailyScannerInstance]  # alle IPs der Gruppe, sortiert nach ip; leer bei "unknown" (zu groß)
    protocols: dict[Protocol, ProtocolResult]  # alle Protokolle; ohne Kontakt beide Level 0
    traffic: DailyTraffic


@dataclass
class DailyResult:
    """Ergebnis eines einzelnen Tages."""

    schema_version: int  # Version dieser Datenstruktur
    date: dt.date  # Tag der Daten
    generated_at: dt.datetime  # Zeitpunkt der Erzeugung dieser Datei (UTC)
    sensors: list[DailySensor]  # alle Sensoren, auch ohne Verbindungen
    actors: list[DailyActor]  # Scanner-Gruppen; "unknown" nur mit analyse_unkown
