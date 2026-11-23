<?php

declare(strict_types=1);

namespace Viewer\View;

use Viewer\Model\ProtocolResult;

/** Netzdiagramm der Protokoll-Scores als Inline-SVG. */
final class Radar
{
    private const MARGIN = 30;
    private const RINGS = [0.25, 0.5, 0.75, 1.0];

    /** @param array<string, ProtocolResult> $protocols */
    public static function svg(array $protocols, int $size = 204): string
    {
        $axes = Levels::PROTOCOLS;
        $n = count($axes);
        $c = $size / 2;
        $r = $c - self::MARGIN;
        $angles = array_map(fn (int $i) => 2 * M_PI * $i / $n - M_PI / 2, range(0, $n - 1));
        $point = fn (float $a, float $f) => [$c + $r * $f * cos($a), $c + $r * $f * sin($a)];
        $poly = fn (array $pts) => implode(' ', array_map(fn ($p) => sprintf('%.1f,%.1f', ...$p), $pts));

        $out = sprintf('<svg class="radar" viewBox="0 0 %1$d %1$d" width="%1$d" height="%1$d" role="img">', $size);

        foreach (self::RINGS as $f) {
            $out .= sprintf('<polygon class="ring" points="%s"/>', $poly(array_map(fn ($a) => $point($a, $f), $angles)));
        }

        foreach ($angles as $i => $a) {
            [$x, $y] = $point($a, 1.0);
            $out .= sprintf('<line class="axis" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>', $c, $c, $x, $y);

            [$lx, $ly] = [$c + ($r + 5) * cos($a), $c + ($r + 5) * sin($a)];
            $anchor = cos($a) > 0.1 ? 'start' : (cos($a) < -0.1 ? 'end' : 'middle');
            $baseline = sin($a) < -0.1 ? 'text-after-edge' : (sin($a) > 0.1 ? 'hanging' : 'middle');
            $out .= sprintf(
                '<text class="label" x="%.1f" y="%.1f" text-anchor="%s" dominant-baseline="%s">%s</text>',
                $lx,
                $ly,
                $anchor,
                $baseline,
                strtoupper($axes[$i]),
            );
        }

        $scores = array_map(fn (string $p) => min(1.0, max(0.0, $protocols[$p]->score ?? 0.0)), $axes);
        $data = array_map(fn (float $a, float $s) => $point($a, $s), $angles, $scores);
        $out .= sprintf('<polygon class="area" points="%s"/>', $poly($data));

        foreach ($data as $i => [$x, $y]) {
            $p = $axes[$i];
            $res = $protocols[$p] ?? null;
            $title = $res === null ? strtoupper($p) . ': –' : sprintf(
                '%s: score %.2f · %s · %s',
                strtoupper($p),
                $res->score,
                Levels::transport($res->maxTransportLevel),
                Levels::application($p, $res->maxApplicationLevel),
            );
            $out .= sprintf('<circle class="dot" cx="%.1f" cy="%.1f" r="3"><title>%s</title></circle>', $x, $y, Html::e($title));
        }

        return $out . '</svg>';
    }
}
