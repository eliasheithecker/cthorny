<?php
/**
 * @var array{window: string, sort: string, type: ?string, date: ?string} $query
 * @var ?Viewer\View\Timeline $timeline
 * @var ?string $notice
 * @var ?Viewer\Model\AggregatedResult $result
 * @var ?Viewer\Model\Window $window
 * @var list<Viewer\View\ActorCard> $cards
 * @var array<string, int> $typeCounts
 * @var list<Viewer\Model\WindowSensor> $sensors
 * @var array<string, int> $groupsPerSensor Sensor-IP => Anzahl Scanner-Gruppen
 * @var array<string, Viewer\Model\WindowSensor> $sensorsByIp Sensor-IP => jüngster Descriptor
 * @var ?string $error
 */

use Viewer\View\ActorCard;
use Viewer\View\Html;
use Viewer\View\Radar;

$e = Html::e(...);
?>
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Scanner Quartett</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
<header>
    <h1>Scanner Quartett</h1>
    <?php if ($result !== null && $window !== null && $timeline !== null): ?>
        <?php $asOf = $result->asOf->format('Y-m-d') ?>
        <section class="timeline" aria-label="Timeline">
            <div class="timeline-head">
                <div class="timeline-field">
                    <span class="tile-label">Results as of</span>
                    <div class="as-of-nav">
                        <?php if ($timeline->prev): ?>
                            <a class="step" href="<?= $e(Html::url($query, ['date' => $timeline->prev])) ?>" title="Previous result (<?= $e($timeline->prev) ?>)">‹</a>
                        <?php else: ?>
                            <span class="step disabled">‹</span>
                        <?php endif ?>
                        <form method="get" class="date-form">
                            <?php foreach (['window', 'sort', 'type'] as $k): ?>
                                <?php if ($query[$k] !== null): ?><input type="hidden" name="<?= $k ?>" value="<?= $e($query[$k]) ?>"><?php endif ?>
                            <?php endforeach ?>
                            <input type="date" name="date" value="<?= $e($asOf) ?>"
                                   min="<?= $e($timeline->first) ?>" max="<?= $e($timeline->last) ?>"
                                   onchange="this.form.submit()" aria-label="Date">
                            <noscript><button type="submit">Show</button></noscript>
                        </form>
                        <?php if ($timeline->next): ?>
                            <a class="step" href="<?= $e(Html::url($query, ['date' => $timeline->next])) ?>" title="Next result (<?= $e($timeline->next) ?>)">›</a>
                        <?php else: ?>
                            <span class="step disabled">›</span>
                        <?php endif ?>
                        <?php if ($asOf !== $timeline->last): ?>
                            <a class="latest" href="<?= $e(Html::url($query, ['date' => null])) ?>">Latest</a>
                        <?php endif ?>
                    </div>
                </div>
                <div class="timeline-field">
                    <span class="tile-label">Window</span>
                    <div class="window-switch">
                        <?php foreach (['rolling' => ['last_7d', 'last_31d', 'last_365d'], 'all' => ['all']] as $group => $names): ?>
                            <div class="segmented <?= $group ?>" role="group"
                                 aria-label="<?= $group === 'rolling' ? 'Rolling window, counted back from the selected day' : 'Everything since the first result' ?>">
                                <?php foreach ($names as $name): ?>
                                    <?php if ($result->hasWindow($name)): ?>
                                        <a href="<?= $e(Html::url($query, ['window' => $name])) ?>"
                                           class="<?= $query['window'] === $name ? 'active' : '' ?>"><?= $e(WINDOW_LABELS[$name]) ?></a>
                                    <?php else: ?>
                                        <span class="disabled" title="Not available for this date"><?= $e(WINDOW_LABELS[$name]) ?></span>
                                    <?php endif ?>
                                <?php endforeach ?>
                            </div>
                        <?php endforeach ?>
                    </div>
                </div>
                <div class="timeline-field">
                    <span class="tile-label">Range</span>
                    <strong><?= $e($window->start->format('Y-m-d')) ?> – <?= $e($window->end->format('Y-m-d')) ?></strong>
                    <span class="sub"><?= $e($window->coverage->daysIncluded) ?> / <?= $e($window->coverage->daysExpected) ?> days with data</span>
                </div>
                <div class="timeline-field">
                    <span class="tile-label">Sensors</span>
                    <strong><?= $e($window->sensorIpCount()) ?></strong>
                    <span class="sub">generated <?= $e($result->generatedAt->format('Y-m-d H:i')) ?> UTC</span>
                </div>
            </div>

            <div class="track <?= $query['window'] === 'all' ? 'window-all' : '' ?>">
                <?php foreach ($timeline->days as $day): ?>
                    <?php
                    $cls = 'day' . ($day['available'] ? '' : ' missing') . ($day['inWindow'] ? ' in-window' : '')
                        . ($day['selected'] ? ' selected' : '') . ($day['month'] ? ' month-start' : '')
                        . ($day['weekend'] ? ' weekend' : '') . ($day['yearStart'] ? ' year-start' : '');
                    $inner = '<span class="bar"></span><span class="num">' . $day['day'] . '</span>'
                        . ($day['month'] ? '<span class="month">' . $e($day['month']) . '</span>' : '');
                    ?>
                    <?php if ($day['available']): ?>
                        <a class="<?= $cls ?>" href="<?= $e(Html::url($query, ['date' => $day['date']])) ?>" title="<?= $e($day['date']) ?>"><?= $inner ?></a>
                    <?php else: ?>
                        <span class="<?= $cls ?>" title="<?= $e($day['date']) ?> – no result"><?= $inner ?></span>
                    <?php endif ?>
                <?php endforeach ?>
            </div>
            <ul class="legend track-legend">
                <li><span class="swatch sel"></span>Selected day</li>
                <?php if ($query['window'] === 'all'): ?>
                    <li><span class="swatch win-all"></span>All time (since first result)</li>
                <?php else: ?>
                    <li><span class="swatch win"></span>In window (<?= $e(WINDOW_LABELS[$query['window']]) ?> back from selected day)</li>
                <?php endif ?>
                <li><span class="swatch avail"></span>Result available</li>
                <li><span class="swatch none"></span>No result</li>
            </ul>
        </section>

        <?php if ($notice !== null): ?>
            <p class="warning"><?= $e($notice) ?></p>
        <?php endif ?>
        <?php if (!$window->coverage->isComplete()): ?>
            <p class="warning" title="<?= $e(implode(', ', array_map(fn ($d) => $d->format('Y-m-d'), $window->coverage->daysMissing))) ?>">
                <?= $e(count($window->coverage->daysMissing)) ?> day(s) missing in this window
            </p>
        <?php endif ?>
    <?php endif ?>
</header>

<?php if ($error !== null): ?>
    <p class="error">No data available: <?= $e($error) ?></p>
<?php else: ?>
    <nav class="controls">
        <div class="filters">
            <div class="group" aria-label="Type">
                <a href="<?= $e(Html::url($query, ['type' => null])) ?>"
                   class="<?= $query['type'] === null ? 'active' : '' ?>">All <small><?= $e(array_sum($typeCounts)) ?></small></a>
                <?php foreach ($typeCounts as $type => $count): ?>
                    <a href="<?= $e(Html::url($query, ['type' => $type])) ?>"
                       class="chip <?= $e(ActorCard::classForType((string) $type)) ?> <?= $query['type'] === (string) $type ? 'active' : '' ?>">
                        <?= $e($type) ?> <small><?= $e($count) ?></small></a>
                <?php endforeach ?>
            </div>
            <div class="group" aria-label="Sort">
                <span>Sort:</span>
                <?php foreach (ActorCard::SORTS as $key => $label): ?>
                    <a href="<?= $e(Html::url($query, ['sort' => $key])) ?>"
                       class="<?= $query['sort'] === $key ? 'active' : '' ?>"><?= $e($label) ?></a>
                <?php endforeach ?>
            </div>
        </div>

        <button type="button" class="action" popovertarget="sensors-modal">
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                <rect x="1.5" y="2.5" width="13" height="11" rx="1.5"/>
                <path d="M1.5 6.5h13M1.5 10h13M6 6.5v7"/>
            </svg>
            Sensor list <span class="count"><?= $e(count($sensors)) ?></span>
        </button>
    </nav>

    <?php if ($cards === []): ?>
        <p class="empty">No scanner groups observed in this window.</p>
    <?php endif ?>

    <main class="cards">
        <?php foreach ($cards as $card): ?>
            <?php $a = $card->actor ?>
            <article class="card <?= $e($card->typeClass()) ?>">
                <div class="card-top">
                    <span class="card-type"><?= $e($card->type) ?></span>
                    <span class="trump" title="Sum of the four protocol scores (max. 4)">Σ <?= $e(number_format($card->totalScore, 2)) ?></span>
                </div>
                <div class="card-name"><?= $e($a->id) ?></div>
                <div class="card-id"><?= $e($a->editorialSuffix ?? ($a->iscIds !== [] ? 'ISC: ' . implode(', ', $a->iscIds) : $a->idSource)) ?></div>

                <?= Radar::svg($a->protocols) ?>

                <table class="stats">
                    <?php foreach ($card->stats as $label => $value): ?>
                        <tr>
                            <td><?= $e($label) ?></td>
                            <td><?= $e($value) ?></td>
                        </tr>
                    <?php endforeach ?>
                </table>

                <button type="button" class="more" popovertarget="<?= $e($card->domId()) ?>">
                    More <span aria-hidden="true">→</span>
                </button>
            </article>
            <?php require __DIR__ . '/actor_detail.php' ?>
        <?php endforeach ?>
    </main>

    <div id="sensors-modal" class="modal" popover>
        <div class="modal-head">
            <div>
                <h2>Sensors</h2>
                <p class="meta">
                    <?= $e($window->start->format('Y-m-d')) ?> – <?= $e($window->end->format('Y-m-d')) ?>
                    · <?= $e(count($sensors)) ?> descriptors on <?= $e($window->sensorIpCount()) ?> IPs
                    · <?= $e(Html::number(array_sum(array_map(fn ($s) => $s->connectionsTotal, $sensors)))) ?> connections
                </p>
            </div>
            <button type="button" class="close" popovertarget="sensors-modal" popovertargetaction="hide" aria-label="Close">×</button>
        </div>
        <div class="modal-body">
            <table class="sensors">
                <thead>
                <tr>
                    <th>Hostname</th>
                    <th>Region</th>
                    <th>IPv4</th>
                    <th>IPv6</th>
                    <th>Created (UTC)</th>
                    <th class="num">Connections</th>
                    <th class="num">Full</th>
                    <th class="num">Half-open</th>
                    <th class="num" title="Scanner groups that contacted this sensor IP">Groups</th>
                </tr>
                </thead>
                <tbody>
                <?php foreach ($sensors as $s): ?>
                    <tr class="<?= $s->connectionsTotal === 0 ? 'muted' : '' ?>">
                        <td><?= $e($s->hostname) ?></td>
                        <td><?= $e($s->region) ?></td>
                        <td class="mono"><?= $e($s->ipv4) ?></td>
                        <td class="mono"><?= $e($s->ipv6) ?></td>
                        <td><?= $e($s->creation->format('Y-m-d H:i')) ?></td>
                        <td class="num"><?= $e(Html::number($s->connectionsTotal)) ?></td>
                        <td class="num"><?= $e(Html::number($s->connectionsFull)) ?></td>
                        <td class="num"><?= $e(Html::number($s->connectionsHalfOpen)) ?></td>
                        <td class="num"><?= $e($groupsPerSensor[$s->ipv4] ?? 0) ?></td>
                    </tr>
                <?php endforeach ?>
                </tbody>
            </table>
        </div>
    </div>
<?php endif ?>
<script>
    // Zeitstrahl horizontal so scrollen, dass der gewählte Tag mittig steht
    (() => {
        const track = document.querySelector('.track');
        const sel = track?.querySelector('.selected');
        if (track && sel && track.scrollWidth > track.clientWidth) {
            track.scrollLeft = sel.offsetLeft - track.offsetLeft - track.clientWidth / 2;
        }
    })();

    // IP-Tabelle im Detail-Modal nach Text filtern
    document.addEventListener('input', (ev) => {
        const input = ev.target.closest('.ip-filter input');
        const table = input && document.getElementById(input.dataset.table);
        if (!table) return;
        const q = input.value.trim().toLowerCase();
        let shown = 0;
        for (const row of table.tBodies[0].rows) {
            row.hidden = q !== '' && !row.textContent.toLowerCase().includes(q);
            shown += row.hidden ? 0 : 1;
        }
        input.nextElementSibling.textContent = q === '' ? '' : `${shown} / ${table.tBodies[0].rows.length}`;
    });
</script>
</body>
</html>
