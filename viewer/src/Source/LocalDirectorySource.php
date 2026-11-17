<?php

declare(strict_types=1);

namespace Viewer\Source;

use JsonException;
use Throwable;
use Viewer\Model\AggregatedResult;

/** Liest die aggregierten Dateien aus <results>/aggregated/YYYY-MM-DD.json im lokalen Dateisystem. */
final readonly class LocalDirectorySource implements AggregatedSource
{
    private const DATE_PATTERN = '/^\d{4}-\d{2}-\d{2}$/';

    /** @param string $resultsDir Verzeichnis, das aggregated/ enthält */
    public function __construct(private string $resultsDir)
    {
    }

    public function dates(): array
    {
        $dir = $this->aggregatedDir();
        if (!is_dir($dir)) {
            throw new SourceException("Verzeichnis nicht gefunden: $dir");
        }

        $dates = [];
        foreach (scandir($dir) ?: [] as $file) {
            $date = basename($file, '.json');
            if (str_ends_with($file, '.json') && preg_match(self::DATE_PATTERN, $date)) {
                $dates[] = $date;
            }
        }
        sort($dates);
        return $dates;
    }

    public function load(string $date): AggregatedResult
    {
        if (!preg_match(self::DATE_PATTERN, $date)) {
            throw new SourceException("Ungültiges Datum: $date");
        }
        $path = $this->aggregatedDir() . "/$date.json";
        if (!is_readable($path)) {
            throw new SourceException("Datei nicht gefunden: $path");
        }

        try {
            $data = json_decode((string) file_get_contents($path), true, flags: JSON_THROW_ON_ERROR);
            return AggregatedResult::fromArray($data);
        } catch (JsonException $e) {
            throw new SourceException("Ungültiges JSON in $path: {$e->getMessage()}", previous: $e);
        } catch (Throwable $e) {
            throw new SourceException("Unerwartete Struktur in $path: {$e->getMessage()}", previous: $e);
        }
    }

    public function describe(): string
    {
        return $this->aggregatedDir();
    }

    private function aggregatedDir(): string
    {
        return rtrim($this->resultsDir, '/') . '/aggregated';
    }
}
