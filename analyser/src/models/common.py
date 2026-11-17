"""Gemeinsame Typen der Output-Datenstruktur, siehe idee.md."""

from dataclasses import dataclass
from typing import Self

from .levels import APPLICATION_LEVELS, TRANSPORT_MAX, ApplicationLevel, Protocol, TransportLevel

SCHEMA_VERSION = 2

# id aus scanners.csv
ActorId = str


@dataclass
class ProtocolResult:
    """Interaktionstiefe eines Scanners auf einem Protokoll."""

    max_transport_level: TransportLevel  # höchstes erreichtes Transport-Level
    # höchstes erreichtes Application-Level; kann aus einem anderen Event stammen als das Transport-Maximum
    max_application_level: ApplicationLevel
    score: float  # Interaktions-Score von 0 bis 1 aus beiden Maxima

    @classmethod
    def from_levels(
        cls,
        protocol: Protocol,
        max_transport_level: TransportLevel,
        max_application_level: ApplicationLevel,
    ) -> Self:
        """Berechnet den Score aus den Maxima, gilt für Tage und Zeitfenster."""
        transport_max = TRANSPORT_MAX[protocol]
        application_levels = APPLICATION_LEVELS[protocol]
        if max_transport_level > transport_max:
            raise ValueError(f"{protocol}: {max_transport_level!r} gibt es nicht")
        if not isinstance(max_application_level, application_levels):
            raise ValueError(f"{protocol}: {max_application_level!r} gibt es nicht")
        return cls(
            max_transport_level=max_transport_level,
            max_application_level=max_application_level,
            score=0.3 * max_transport_level / transport_max
            + 0.7 * max_application_level / max(application_levels),
        )
