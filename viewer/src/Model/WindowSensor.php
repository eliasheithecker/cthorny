<?php

declare(strict_types=1);

namespace Viewer\Model;

use DateTimeImmutable;

/** Ein Sensor (Descriptor) im Zeitfenster; Schlüssel ist ipv4 + creation. */
final readonly class WindowSensor
{
    public function __construct(
        public string $hostname,
        public string $ipv4,
        public string $ipv6,
        public DateTimeImmutable $creation,
        public string $region,
        public int $connectionsTotal,
        public int $connectionsFull,
        public int $connectionsHalfOpen,
    ) {
    }

    public static function fromArray(array $data): self
    {
        return new self(
            hostname: $data['hostname'],
            ipv4: $data['ipv4'],
            ipv6: $data['ipv6'],
            creation: new DateTimeImmutable($data['creation']),
            region: $data['region'],
            connectionsTotal: (int) $data['connections_total'],
            connectionsFull: (int) $data['connections_full'],
            connectionsHalfOpen: (int) $data['connections_half_open'],
        );
    }
}
