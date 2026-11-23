<?php

declare(strict_types=1);

namespace Viewer\Model;

use DateTimeImmutable;

/** Ergebnis eines Zeitfensters. */
final readonly class Window
{
    /** Alle bekannten Fenster in Anzeigereihenfolge; rollierende Fenster zuerst, dann all. */
    public const NAMES = ['last_7d', 'last_31d', 'last_365d', 'all'];

    /** Fenster, die jede aggregierte Datei enthalten muss; last_365d ist optional (ältere Dateien). */
    public const REQUIRED = ['last_7d', 'last_31d', 'all'];

    /**
     * @param list<WindowSensor> $sensors
     * @param list<WindowActor> $actors
     */
    public function __construct(
        public DateTimeImmutable $start,
        public DateTimeImmutable $end,
        public Coverage $coverage,
        public array $sensors,
        public array $actors,
    ) {
    }

    public static function fromArray(array $data): self
    {
        return new self(
            start: new DateTimeImmutable($data['start']),
            end: new DateTimeImmutable($data['end']),
            coverage: Coverage::fromArray($data['coverage']),
            sensors: array_map(WindowSensor::fromArray(...), $data['sensors']),
            actors: array_map(WindowActor::fromArray(...), $data['actors']),
        );
    }

    /** Anzahl verschiedener Sensor-IPs; ein Sensor kann mehrere Descriptoren haben. */
    public function sensorIpCount(): int
    {
        return count(array_unique(array_map(fn (WindowSensor $s) => $s->ipv4, $this->sensors)));
    }
}
