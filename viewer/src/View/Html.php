<?php

declare(strict_types=1);

namespace Viewer\View;

final class Html
{
    public static function e(string|int|float|null $value): string
    {
        return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }

    /** Link auf die aktuelle Seite mit geänderten Query-Parametern; null entfernt einen Parameter. */
    public static function url(array $current, array $overrides): string
    {
        $query = array_filter(array_merge($current, $overrides), fn ($v) => $v !== null && $v !== '');
        return '?' . http_build_query($query);
    }

    public static function number(int $n): string
    {
        return number_format($n, 0, '.', ',');
    }

    /** Prozent mit höchstens zwei Nachkommastellen, z. B. 100%, 56.61%. */
    public static function percent(int $part, int $whole): string
    {
        if ($whole === 0) {
            return '–';
        }
        return rtrim(rtrim(number_format(100 * $part / $whole, 2, '.', ''), '0'), '.') . '%';
    }
}
