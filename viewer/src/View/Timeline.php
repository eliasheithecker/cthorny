<?php

declare(strict_types=1);

namespace Viewer\View;

use DateInterval;
use DatePeriod;
use DateTimeImmutable;
use Viewer\Model\Window;

/** Zeitstrahl über alle Stichtage: ein Eintrag pro Kalendertag, mit gewähltem Stichtag und Fensterband. */
final readonly class Timeline
{
    /**
     * @param list<array{
     *     date: string, day: int, weekend: bool, available: bool, inWindow: bool, selected: bool,
     *     month: ?string, yearStart: bool
     * }> $days month: Beschriftung am Monatsanfang, yearStart: 1. Januar (Trennlinie im Zeitstrahl)
     */
    public function __construct(
        public array $days,
        public ?string $prev, // vorheriger verfügbarer Stichtag
        public ?string $next, // nächster verfügbarer Stichtag
        public string $first,
        public string $last,
    ) {
    }

    /**
     * Wählt den Stichtag: den angefragten, sonst den letzten verfügbaren davor (oder den ersten),
     * ohne Anfrage den neuesten.
     *
     * @param list<string> $dates aufsteigend sortiert, nicht leer
     * @return array{0: string, 1: ?string} Stichtag und ggf. Hinweis für die Anzeige
     */
    public static function resolve(array $dates, ?string $requested): array
    {
        $latest = $dates[array_key_last($dates)];
        if ($requested === null || $requested === '') {
            return [$latest, null];
        }
        if (in_array($requested, $dates, true)) {
            return [$requested, null];
        }
        if (DateTimeImmutable::createFromFormat('!Y-m-d', $requested) === false) {
            return [$latest, "Invalid date '$requested', showing the latest result."];
        }

        $before = array_filter($dates, fn (string $d) => $d < $requested);
        $chosen = $before === [] ? $dates[0] : $before[array_key_last($before)];
        return [$chosen, "No result for $requested, showing the nearest available day $chosen."];
    }

    /** @param list<string> $dates aufsteigend sortiert, nicht leer */
    public static function build(array $dates, string $asOf, Window $window): self
    {
        $available = array_flip($dates);
        $windowStart = $window->start->format('Y-m-d');
        $windowEnd = $window->end->format('Y-m-d');

        // Fenster, die vor den ersten Stichtag reichen, sollen sichtbar bleiben
        $start = new DateTimeImmutable(min($dates[0], $windowStart));
        $end = new DateTimeImmutable($dates[array_key_last($dates)]);

        $days = [];
        foreach (new DatePeriod($start, new DateInterval('P1D'), $end->modify('+1 day')) as $day) {
            $d = $day->format('Y-m-d');
            $first = $days === [];
            $monthStart = $day->format('j') === '1';
            $days[] = [
                'date' => $d,
                'day' => (int) $day->format('j'),
                'weekend' => (int) $day->format('N') >= 6,
                'available' => isset($available[$d]),
                'inWindow' => $d >= $windowStart && $d <= $windowEnd,
                'selected' => $d === $asOf,
                // Jahr nur am Anfang und im Januar, sonst nur der Monat
                'month' => $first || $monthStart
                    ? $day->format($first || $day->format('n') === '1' ? 'M Y' : 'M')
                    : null,
                'yearStart' => !$first && $day->format('z') === '0',
            ];
        }

        $index = array_search($asOf, $dates, true);
        return new self(
            days: $days,
            prev: $dates[$index - 1] ?? null,
            next: $dates[$index + 1] ?? null,
            first: $dates[0],
            last: $dates[array_key_last($dates)],
        );
    }
}
