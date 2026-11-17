<?php

declare(strict_types=1);

namespace Viewer;

use Viewer\Source\AggregatedSource;
use Viewer\Source\LocalDirectorySource;

/** Konfiguration über Umgebungsvariablen. */
final class Config
{
    public const DEFAULT_RESULTS_DIR = 'data/results';

    /** VIEWER_RESULTS_DIR: Verzeichnis mit aggregated/YYYY-MM-DD.json, relativ zu viewer/ oder absolut. */
    public static function source(): AggregatedSource
    {
        // TODO: VIEWER_SOURCE=s3 mit Bucket/Prefix, sobald Schritt 7 (s7_publish) in den S3 schreibt
        $dir = getenv('VIEWER_RESULTS_DIR') ?: self::DEFAULT_RESULTS_DIR;
        if (!str_starts_with($dir, '/')) {
            $dir = dirname(__DIR__) . '/' . $dir;
        }

        return new LocalDirectorySource($dir);
    }
}
