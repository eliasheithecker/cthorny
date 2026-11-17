<?php

declare(strict_types=1);

namespace Viewer\View;

/** Anzeigenamen der Levels; muss zu analyser/src/models/levels.py passen. */
final class Levels
{
    public const PROTOCOLS = ['ssh', 'smtp', 'telnet', 'ldap'];

    private const TRANSPORT = [
        0 => '–',
        1 => 'SYN',
        2 => 'Handshake',
        3 => 'TLS tested',
        4 => 'TLS used',
    ];

    private const APPLICATION = [
        'ssh' => [0 => '–', 1 => 'Banner', 2 => 'Login', 3 => 'Command', 4 => 'Sudo'],
        'telnet' => [0 => '–', 1 => 'Login', 2 => 'Command', 3 => 'Sudo'],
        'smtp' => [0 => '–', 1 => 'Command', 2 => 'Capability', '2.5' => 'VRFY/EXPN', 3 => 'MAIL', 4 => 'AUTH'],
        'ldap' => [0 => '–', 1 => 'Command', 2 => 'Anon. bind', 3 => 'Search', 4 => 'Cred. bind'],
    ];

    /** TRANSPORT_MAX in levels.py: TLS gibt es nur bei SMTP und LDAP. */
    private const TRANSPORT_MAX = ['ssh' => 2, 'telnet' => 2, 'smtp' => 4, 'ldap' => 4];

    public const NAMES = ['ssh' => 'SSH', 'smtp' => 'SMTP', 'telnet' => 'Telnet', 'ldap' => 'LDAP'];

    /** @return array<string, string> Stufen ab 1 bis zum Maximum des Protokolls: Level => Name */
    public static function transportSteps(string $protocol): array
    {
        return array_slice(self::TRANSPORT, 1, self::TRANSPORT_MAX[$protocol] ?? 4, true);
    }

    /** @return array<string, string> Stufen ab 1: Level => Name */
    public static function applicationSteps(string $protocol): array
    {
        return array_slice(self::APPLICATION[$protocol] ?? [], 1, null, true);
    }

    public static function transport(int $level): string
    {
        return self::TRANSPORT[$level] ?? (string) $level;
    }

    public static function application(string $protocol, float $level): string
    {
        // (string) 2.0 === "2" und (string) 2.5 === "2.5" passen zu den Array-Schlüsseln
        $key = (string) $level;
        return self::APPLICATION[$protocol][$key] ?? $key;
    }
}
