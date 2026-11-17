<?php

declare(strict_types=1);

namespace Viewer\Model;

use DateTimeImmutable;
use UnexpectedValueException;

/** Stand aller Zeitfenster an einem Tag; Gegenstück zu AggregatedResult in analyser/src/models/aggregated.py. */
final readonly class AggregatedResult
{
    public const SCHEMA_VERSION = 2;

    /** @param array<string, Window> $windows Schlüssel aus Window::NAMES; last_365d kann fehlen */
    public function __construct(
        public int $schemaVersion,
        public DateTimeImmutable $asOf,
        public DateTimeImmutable $generatedAt,
        public array $windows,
    ) {
    }

    public static function fromArray(array $data): self
    {
        $version = (int) ($data['schema_version'] ?? 0);
        if ($version !== self::SCHEMA_VERSION) {
            throw new UnexpectedValueException(
                sprintf('schema_version %d wird nicht unterstützt (erwartet %d)', $version, self::SCHEMA_VERSION)
            );
        }

        $windows = [];
        foreach (Window::NAMES as $name) {
            if (isset($data['windows'][$name])) {
                $windows[$name] = Window::fromArray($data['windows'][$name]);
            } elseif (in_array($name, Window::REQUIRED, true)) {
                throw new UnexpectedValueException("Fenster '$name' fehlt");
            }
        }

        return new self(
            schemaVersion: $version,
            asOf: new DateTimeImmutable($data['as_of']),
            generatedAt: new DateTimeImmutable($data['generated_at']),
            windows: $windows,
        );
    }

    public function hasWindow(string $name): bool
    {
        return isset($this->windows[$name]);
    }

    public function window(string $name): Window
    {
        return $this->windows[$name] ?? throw new UnexpectedValueException("Unbekanntes Fenster '$name'");
    }
}
