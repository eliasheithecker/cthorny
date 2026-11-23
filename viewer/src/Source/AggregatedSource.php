<?php

declare(strict_types=1);

namespace Viewer\Source;

use Viewer\Model\AggregatedResult;

/**
 * Liefert die aggregierten Dateien, eine pro Stichtag (as_of); lokal oder später aus dem S3.
 * Ablage wie in analyser/idee.md (Schritt 14): results/aggregated/YYYY-MM-DD.json
 */
interface AggregatedSource
{
    /**
     * @return list<string> verfügbare Stichtage als Y-m-d, aufsteigend sortiert
     * @throws SourceException
     */
    public function dates(): array;

    /** @throws SourceException wenn die Datei fehlt oder nicht lesbar ist */
    public function load(string $date): AggregatedResult;

    /** Für Fehlermeldungen, z. B. Pfad oder S3-URI. */
    public function describe(): string;
}
