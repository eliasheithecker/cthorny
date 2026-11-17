<?php

declare(strict_types=1);

namespace Viewer\Model;

use DateTimeImmutable;

/** Eine Scanner-IP einer Gruppe im Zeitfenster; Schlüssel ist ip (innerhalb der Gruppe). */
final readonly class WindowScannerInstance
{
    public function __construct(
        public string $ip,
        public ?string $hostname, // PTR-Hostname, jüngster Stand; null ohne PTR-Record
        public string $dnsStatus, // Status der PTR-Abfrage, z. B. NOERROR, NXDOMAIN; jüngster Stand
        public bool $fcrdnsValid, // Hostname löst wieder auf diese IP auf; jüngster Stand
        public ?string $iscId, // ISC-Name dieser IP, falls gelistet; jüngster Stand
        public DateTimeImmutable $firstSeen,
        public DateTimeImmutable $lastSeen,
        public int $daysSeen,
    ) {
    }

    public static function fromArray(array $data): self
    {
        return new self(
            ip: $data['ip'],
            hostname: $data['hostname'] ?? null,
            dnsStatus: $data['dns_status'],
            fcrdnsValid: (bool) $data['fcrdns_valid'],
            iscId: $data['isc_id'] ?? null,
            firstSeen: new DateTimeImmutable($data['first_seen']),
            lastSeen: new DateTimeImmutable($data['last_seen']),
            daysSeen: (int) $data['days_seen'],
        );
    }
}
