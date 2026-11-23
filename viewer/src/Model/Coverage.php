<?php

declare(strict_types=1);

namespace Viewer\Model;

use DateTimeImmutable;

/** Zeigt, wie vollständig ein Fenster ist. */
final readonly class Coverage
{
    /** @param list<DateTimeImmutable> $daysMissing */
    public function __construct(
        public int $daysExpected,
        public int $daysIncluded,
        public array $daysMissing,
    ) {
    }

    public static function fromArray(array $data): self
    {
        return new self(
            daysExpected: (int) $data['days_expected'],
            daysIncluded: (int) $data['days_included'],
            daysMissing: array_map(fn (string $d) => new DateTimeImmutable($d), $data['days_missing']),
        );
    }

    public function isComplete(): bool
    {
        return $this->daysIncluded >= $this->daysExpected;
    }
}
