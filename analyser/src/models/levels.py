"""Protokolle und Levels, siehe Abschnitt "Levels" in idee.md."""

from enum import Enum, IntEnum, StrEnum


class Protocol(StrEnum):
    """Untersuchte Protokolle (Ports 22, 23, 25, 389)."""

    SSH = "ssh"
    TELNET = "telnet"
    SMTP = "smtp"
    LDAP = "ldap"


class TransportLevel(IntEnum):
    NO_CONNECTION = 0
    SYN = 1
    HANDSHAKE = 2
    TLS_TESTED = 3  # nur SMTP und LDAP
    TLS_USED = 4  # nur SMTP und LDAP


class SshLevel(IntEnum):
    NOT_USED = 0
    BANNER = 1
    LOGIN = 2
    COMMAND = 3
    SUDO = 4


class TelnetLevel(IntEnum):
    NOT_USED = 0
    LOGIN = 1
    COMMAND = 2
    SUDO = 3


class SmtpLevel(float, Enum):
    NOT_USED = 0
    COMMAND = 1
    CAPABILITY = 2
    VRFY_EXPN = 2.5
    MAIL = 3
    AUTH = 4


class LdapLevel(IntEnum):
    NOT_USED = 0
    COMMAND = 1
    ANONYMOUS_BIND = 2
    SEARCH = 3
    CREDENTIAL_BIND = 4


ApplicationLevel = SshLevel | TelnetLevel | SmtpLevel | LdapLevel

APPLICATION_LEVELS = {
    Protocol.SSH: SshLevel,
    Protocol.TELNET: TelnetLevel,
    Protocol.SMTP: SmtpLevel,
    Protocol.LDAP: LdapLevel,
}

TRANSPORT_MAX = {
    Protocol.SSH: TransportLevel.HANDSHAKE,
    Protocol.TELNET: TransportLevel.HANDSHAKE,
    Protocol.SMTP: TransportLevel.TLS_USED,
    Protocol.LDAP: TransportLevel.TLS_USED,
}
