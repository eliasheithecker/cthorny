<?php

declare(strict_types=1);

require __DIR__ . '/../vendor/autoload.php';

use Viewer\Config;
use Viewer\Model\Window;
use Viewer\Source\SourceException;
use Viewer\View\ActorCard;
use Viewer\View\Timeline;

// Fenster ohne Auswahl und als Ersatz, wenn ein Fenster fehlt; all ist in jeder Datei vorhanden
const DEFAULT_WINDOW = 'all';

const WINDOW_LABELS = [
    'last_7d' => '7 days',
    'last_31d' => '31 days',
    'last_365d' => '365 days',
    'all' => 'All time',
];

$query = [
    'window' => in_array($_GET['window'] ?? null, Window::NAMES, true) ? $_GET['window'] : DEFAULT_WINDOW,
    'sort' => array_key_exists($_GET['sort'] ?? '', ActorCard::SORTS) ? $_GET['sort'] : 'score',
    'type' => is_string($_GET['type'] ?? null) ? $_GET['type'] : null,
    'date' => is_string($_GET['date'] ?? null) ? $_GET['date'] : null,
];

$source = Config::source();
$result = $window = $timeline = $notice = null;
$cards = $typeCounts = $sensors = $groupsPerSensor = $sensorsByIp = [];
$error = null;

try {
    $dates = $source->dates();
    if ($dates === []) {
        throw new SourceException('Keine aggregierten Dateien in ' . $source->describe());
    }
    [$asOf, $notice] = Timeline::resolve($dates, $query['date']);
    // Ohne explizite Auswahl bleibt die URL ohne Datum und zeigt immer den neuesten Stand
    $query['date'] = $query['date'] === null ? null : $asOf;

    $result = $source->load($asOf);
    if (!$result->hasWindow($query['window'])) {
        $notice = 'The ' . WINDOW_LABELS[$query['window']] . " window is not available for $asOf, showing "
            . strtolower(WINDOW_LABELS[DEFAULT_WINDOW]) . '.';
        $query['window'] = DEFAULT_WINDOW;
    }
    $window = $result->window($query['window']);
    $timeline = Timeline::build($dates, $asOf, $window);

    $allCards = array_map(fn ($a) => ActorCard::fromActor($a, $window), $window->actors);
    $typeCounts = array_count_values(array_map(fn (ActorCard $c) => $c->type, $allCards));
    ksort($typeCounts);
    if (!isset($typeCounts[$query['type'] ?? ''])) {
        $query['type'] = null;
    }

    $cards = array_values(array_filter($allCards, fn (ActorCard $c) => $query['type'] === null || $c->type === $query['type']));
    $cards = ActorCard::sort($cards, $query['sort']);

    // Sensoren für das Modal: meiste Verbindungen zuerst
    $sensors = $window->sensors;
    usort($sensors, fn ($x, $y) => [$y->connectionsTotal, $x->hostname, $x->creation]
        <=> [$x->connectionsTotal, $y->hostname, $y->creation]);
    // Sensor-IP => jüngster Descriptor, um sensors_hit in den Details mit Hostname und Region anzuzeigen
    foreach ($window->sensors as $s) {
        if (!isset($sensorsByIp[$s->ipv4]) || $s->creation > $sensorsByIp[$s->ipv4]->creation) {
            $sensorsByIp[$s->ipv4] = $s;
        }
    }
    // Anzahl der Scanner-Gruppen je Sensor-IP (alle Typen, unabhängig vom Filter)
    foreach ($window->actors as $actor) {
        foreach (array_unique($actor->traffic->sensorsHit) as $ip) {
            $groupsPerSensor[$ip] = ($groupsPerSensor[$ip] ?? 0) + 1;
        }
    }
} catch (SourceException $e) {
    http_response_code(503);
    $error = $e->getMessage();
}

require __DIR__ . '/../templates/page.php';
