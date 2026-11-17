<?php

declare(strict_types=1);

namespace Viewer\Model;

use DateTimeImmutable;

/** Eine Scanner-Gruppe im Zeitfenster; Schlüssel ist id_source + id. */
final readonly class WindowActor
{
    public const UNKNOWN = 'unknown';

    /**
     * @param 'editorial'|'isc'|'unknown' $idSource
     * @param list<string> $iscIds
     * @param list<WindowScannerInstance> $instances sortiert nach ip; leer bei "unknown"
     * @param array<string, ProtocolResult> $protocols Schlüssel: ssh, telnet, smtp, ldap
     */
    public function __construct(
        public string $id,
        public string $idSource,
        public ?string $editorialSuffix,
        public ?string $editorialType,
        public array $iscIds,
        public DateTimeImmutable $firstSeen,
        public DateTimeImmutable $lastSeen,
        public int $daysSeen,
        public array $instances,
        public array $protocols,
        public Traffic $traffic,
    ) {
    }

    public static function fromArray(array $data): self
    {
        return new self(
            id: $data['id'],
            idSource: $data['id_source'],
            editorialSuffix: $data['editorial_suffix'] ?? null,
            editorialType: $data['editorial_type'] ?? null,
            iscIds: $data['isc_ids'],
            firstSeen: new DateTimeImmutable($data['first_seen']),
            lastSeen: new DateTimeImmutable($data['last_seen']),
            daysSeen: (int) $data['days_seen'],
            instances: array_map(WindowScannerInstance::fromArray(...), $data['instances']),
            protocols: array_map(ProtocolResult::fromArray(...), $data['protocols']),
            traffic: Traffic::fromArray($data['traffic']),
        );
    }

    /** Die Gruppe "unknown" listet ihre IPs nicht (zu groß). */
    public function isUnknown(): bool
    {
        return $this->idSource === self::UNKNOWN;
    }

    public function ipCount(): int
    {
        return count($this->instances);
    }

    public function fcrdnsValidCount(): int
    {
        return count(array_filter($this->instances, fn (WindowScannerInstance $i) => $i->fcrdnsValid));
    }

    public function hostnameCount(): int
    {
        return count(array_filter($this->instances, fn (WindowScannerInstance $i) => $i->hostname !== null));
    }

    public function iscListedCount(): int
    {
        return count(array_filter($this->instances, fn (WindowScannerInstance $i) => $i->iscId !== null));
    }

    /** @return array<string, int> DNS-Status => Anzahl IPs, häufigster zuerst */
    public function dnsStatusCounts(): array
    {
        $counts = array_count_values(array_map(fn (WindowScannerInstance $i) => $i->dnsStatus, $this->instances));
        arsort($counts);
        return $counts;
    }

    /** @return array<string, int> ISC-Name => Anzahl IPs mit diesem Namen, häufigster zuerst */
    public function iscIdCounts(): array
    {
        $ids = array_filter(array_map(fn (WindowScannerInstance $i) => $i->iscId, $this->instances));
        $counts = array_count_values($ids);
        arsort($counts);
        return $counts;
    }
}
