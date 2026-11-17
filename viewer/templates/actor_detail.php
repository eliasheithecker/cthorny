<?php
/**
 * Detail-Modal einer Scanner-Gruppe; zeigt alle Felder von WindowActor inkl. aller instances.
 *
 * @var Viewer\View\ActorCard $card
 * @var Viewer\Model\WindowActor $a
 * @var Viewer\Model\Window $window
 * @var array<string, Viewer\Model\WindowSensor> $sensorsByIp
 * @var Closure $e
 */

use Viewer\View\Html;
use Viewer\View\Levels;
use Viewer\View\Radar;

$t = $a->traffic;
$ipCount = $a->ipCount();
$fcrdns = $a->fcrdnsValidCount();
$withPtr = $a->hostnameCount();
$iscListed = $a->iscListedCount();
$iscIdCounts = $a->iscIdCounts();
$pct = fn (int|float $part, int|float $whole) => $whole > 0 ? round(100 * $part / $whole, 2) : 0;
$sensorsHit = $t->sensorsHit;
sort($sensorsHit);
$date = fn (DateTimeImmutable $d) => $d->format('Y-m-d');

// Verbindungs-Peaks: Zeile => [Gruppe Tag, Gruppe 1 h, einzelne IP Tag, einzelne IP 1 h], je [Wert, Feldname]
$peaks = [
    'Per sensor' => [
        'sub' => 'one sensor, all ports',
        'group' => [[$t->maxConnPerSensorDay, 'max_conn_per_sensor_day'], [$t->maxConnPerSensor1h, 'max_conn_per_sensor_1h']],
        'ip' => [[$t->maxConnPerInstancePerSensorDay, 'max_conn_per_scanner_instance_per_sensor_day'], [$t->maxConnPerInstancePerSensor1h, 'max_conn_per_scanner_instance_per_sensor_1h']],
    ],
    'Per sensor & port' => [
        'sub' => 'one port of one sensor',
        'group' => [[$t->maxConnPerSensorPortDay, 'max_conn_per_sensor_port_day'], [$t->maxConnPerSensorPort1h, 'max_conn_per_sensor_port_1h']],
        'ip' => [[$t->maxConnPerInstancePerSensorPortDay, 'max_conn_per_scanner_instance_per_sensor_port_day'], [$t->maxConnPerInstancePerSensorPort1h, 'max_conn_per_scanner_instance_per_sensor_port_1h']],
    ],
];
?>
<div id="<?= $e($card->domId()) ?>" class="modal detail <?= $e($card->typeClass()) ?>" popover>
    <div class="modal-head">
        <div>
            <div class="card-type"><?= $e($card->type) ?><?= strcasecmp($card->type, $a->idSource) !== 0 ? ' · ' . $e($a->idSource) : '' ?></div>
            <h2><?= $e($a->id) ?></h2>
            <p class="meta">
                <?= $e($a->editorialSuffix ?? 'no PTR suffix') ?>
                · seen <?= $e($date($a->firstSeen)) ?>
                <?php if ($a->lastSeen != $a->firstSeen): ?>– <?= $e($date($a->lastSeen)) ?><?php endif ?>
            </p>
        </div>
        <div class="head-right">
            <span class="trump big" title="Sum of the four protocol scores (max. 4)">Σ <?= $e(number_format($card->totalScore, 2)) ?></span>
            <button type="button" class="close" popovertarget="<?= $e($card->domId()) ?>" popovertargetaction="hide" aria-label="Close">×</button>
        </div>
    </div>

    <div class="modal-body detail-body">
        <section class="tiles">
            <div class="tile">
                <span class="tile-label">IPs observed</span>
                <?php if ($a->isUnknown()): ?>
                    <span class="tile-value">–</span>
                    <span class="tile-sub">not listed for this group</span>
                <?php else: ?>
                    <span class="tile-value"><?= $e(Html::number($ipCount)) ?></span>
                    <span class="tile-sub"><?= $e(Html::number($withPtr)) ?> with PTR hostname</span>
                <?php endif ?>
            </div>
            <div class="tile">
                <span class="tile-label">FCrDNS valid</span>
                <span class="tile-value"><?= $e(Html::percent($fcrdns, $ipCount)) ?></span>
                <span class="meter"><span style="width: <?= $pct($fcrdns, $ipCount) ?>%"></span></span>
                <span class="tile-sub"><?= $e(Html::number($fcrdns)) ?> of <?= $e(Html::number($ipCount)) ?> IPs (latest state)</span>
            </div>
            <div class="tile">
                <span class="tile-label">ISC listed</span>
                <span class="tile-value"><?= $e(Html::percent($iscListed, $ipCount)) ?></span>
                <span class="meter"><span style="width: <?= $pct($iscListed, $ipCount) ?>%"></span></span>
                <span class="tile-sub"><?= $e(Html::number($iscListed)) ?> of <?= $e(Html::number($ipCount)) ?> IPs on an ISC list</span>
            </div>
            <div class="tile">
                <span class="tile-label">Days seen</span>
                <span class="tile-value"><?= $e($a->daysSeen) ?> <small>/ <?= $e($window->coverage->daysIncluded) ?></small></span>
                <span class="meter"><span style="width: <?= $pct($a->daysSeen, $window->coverage->daysIncluded) ?>%"></span></span>
                <span class="tile-sub">days with data in window</span>
            </div>
            <div class="tile">
                <span class="tile-label">Sensors hit</span>
                <span class="tile-value"><?= $e(Html::number(count($t->sensorsHit))) ?></span>
                <span class="tile-sub">distinct sensor IPs</span>
            </div>
            <div class="tile">
                <span class="tile-label">Connections</span>
                <span class="tile-value"><?= $e(Html::number($t->connectionsTotal)) ?></span>
                <span class="tile-sub"><?= $e(Html::percent($t->connectionsFull, $t->connectionsTotal)) ?> with full handshake</span>
            </div>
        </section>

        <section class="panel">
            <h3>Interaction depth</h3>
            <div class="depth">
                <?= Radar::svg($a->protocols, 220) ?>
                <div class="protocols-detail">
                    <?php foreach (Levels::PROTOCOLS as $p): ?>
                        <?php $res = $a->protocols[$p] ?? null ?>
                        <div class="proto <?= ($res?->score ?? 0) > 0 ? '' : 'muted' ?>">
                            <div class="proto-head">
                                <strong><?= $e(Levels::NAMES[$p]) ?></strong>
                                <span class="meter"><span style="width: <?= $pct($res?->score ?? 0, 1) ?>%"></span></span>
                                <span class="score"><?= $e(number_format($res?->score ?? 0, 2)) ?></span>
                            </div>
                            <div class="ladder">
                                <span class="ladder-label">Transport</span>
                                <ol class="steps">
                                    <?php foreach (Levels::transportSteps($p) as $lvl => $name): ?>
                                        <li class="<?= $res && $lvl <= $res->maxTransportLevel ? 'on' : '' ?> <?= $res && (float) $lvl === (float) $res->maxTransportLevel ? 'max' : '' ?>" title="<?= $e($name) ?>"><?= $e($name) ?></li>
                                    <?php endforeach ?>
                                </ol>
                            </div>
                            <div class="ladder">
                                <span class="ladder-label">Application</span>
                                <ol class="steps">
                                    <?php foreach (Levels::applicationSteps($p) as $lvl => $name): ?>
                                        <li class="<?= $res && (float) $lvl <= $res->maxApplicationLevel ? 'on' : '' ?> <?= $res && (float) $lvl === $res->maxApplicationLevel ? 'max' : '' ?>" title="<?= $e($name) ?>"><?= $e($name) ?></li>
                                    <?php endforeach ?>
                                </ol>
                            </div>
                        </div>
                    <?php endforeach ?>
                </div>
            </div>
            <p class="hint">Score = 0.3 × transport level / max + 0.7 × application level / max, per protocol.</p>
        </section>

        <div class="detail-grid">
            <section class="panel">
                <h3>Traffic</h3>
                <div class="split-bar" title="<?= $e(Html::number($t->connectionsFull)) ?> full · <?= $e(Html::number($t->connectionsHalfOpen)) ?> half-open">
                    <span class="full" style="width: <?= $pct($t->connectionsFull, $t->connectionsTotal) ?>%"></span>
                    <span class="half" style="width: <?= $pct($t->connectionsHalfOpen, $t->connectionsTotal) ?>%"></span>
                </div>
                <ul class="legend">
                    <li><span class="swatch full"></span>Full handshake <b><?= $e(Html::number($t->connectionsFull)) ?></b></li>
                    <li><span class="swatch half"></span>Half-open <b><?= $e(Html::number($t->connectionsHalfOpen)) ?></b></li>
                </ul>

                <h3>Connection peaks</h3>
                <table class="peak-matrix">
                    <thead>
                    <tr>
                        <th rowspan="2"></th>
                        <th colspan="2" class="grp">Whole group <small>all scanner instances together</small></th>
                        <th colspan="2" class="grp">Single scanner instance <small>one instance of the group</small></th>
                    </tr>
                    <tr>
                        <th>Day</th><th>1 h</th>
                        <th>Day</th><th>1 h</th>
                    </tr>
                    </thead>
                    <tbody>
                    <?php foreach ($peaks as $label => $row): ?>
                        <tr>
                            <th scope="row"><?= $e($label) ?> <small><?= $e($row['sub']) ?></small></th>
                            <?php foreach ($row['group'] as [$value, $field]): ?>
                                <td title="<?= $e($field) ?>"><?= $e(Html::number($value)) ?></td>
                            <?php endforeach ?>
                            <?php foreach ($row['ip'] as $i => [$value, $field]): ?>
                                <?php $groupValue = $row['group'][$i][0] ?>
                                <td class="grp" title="<?= $e($field) ?> · <?= $e(Html::percent($value, $groupValue)) ?> of the whole group">
                                    <?= $e(Html::number($value)) ?>
                                    <span class="meter"><span style="width: <?= $pct(min($value, $groupValue), $groupValue) ?>%"></span></span>
                                </td>
                            <?php endforeach ?>
                        </tr>
                    <?php endforeach ?>
                    </tbody>
                </table>
                <p class="hint">
                    Highest number of connections to one sensor (or one sensor port).
                    Day: busiest single day in the window · 1 h: busiest sliding 60-min window.
                    The bar shows the single-instance peak relative to the whole group: full means one scanner instance alone reaches the group peak.
                </p>
            </section>

            <section class="panel">
                <h3>Identity</h3>
                <dl class="facts">
                    <dt>ID</dt><dd class="mono"><?= $e($a->id) ?> <small>(<?= $e($a->idSource) ?>)</small></dd>
                    <dt>Type</dt><dd><?= $e($a->editorialType ?? '–') ?></dd>
                    <dt>PTR suffix</dt><dd class="mono"><?= $e($a->editorialSuffix ?? '–') ?></dd>
                    <dt>ISC lists</dt>
                    <dd>
                        <?php foreach ($a->iscIds as $isc): ?>
                            <span class="tag" title="IPs of this group listed as <?= $e($isc) ?>"><?= $e($isc) ?> <small><?= $e(Html::number($iscIdCounts[$isc] ?? 0)) ?> IPs</small></span>
                        <?php endforeach ?>
                        <?= $a->iscIds === [] ? '–' : '' ?>
                    </dd>
                    <dt>First seen</dt><dd><?= $e($date($a->firstSeen)) ?></dd>
                    <dt>Last seen</dt><dd><?= $e($date($a->lastSeen)) ?></dd>
                    <dt>Days seen</dt><dd><?= $e($a->daysSeen) ?> of <?= $e($window->coverage->daysIncluded) ?> days with data</dd>
                    <?php if (!$a->isUnknown()): ?>
                        <dt>PTR lookup</dt>
                        <dd>
                            <?php foreach ($a->dnsStatusCounts() as $status => $n): ?>
                                <span class="tag <?= $status === 'NOERROR' ? '' : 'warn' ?>"><?= $e($status) ?> <small><?= $e(Html::number($n)) ?></small></span>
                            <?php endforeach ?>
                            <?= $ipCount === 0 ? '–' : '' ?>
                        </dd>
                        <dt>PTR hostname</dt><dd><?= $e(Html::number($withPtr)) ?> of <?= $e(Html::number($ipCount)) ?> IPs</dd>
                        <dt>FCrDNS valid</dt><dd><?= $e(Html::number($fcrdns)) ?> of <?= $e(Html::number($ipCount)) ?> IPs</dd>
                    <?php endif ?>
                </dl>
            </section>
        </div>

        <section class="panel">
            <h3>Sensors hit <small><?= $e(count($sensorsHit)) ?></small></h3>
            <ul class="sensor-chips">
                <?php foreach ($sensorsHit as $ip): ?>
                    <?php $s = $sensorsByIp[$ip] ?? null ?>
                    <li>
                        <?php if ($s): ?><b><?= $e($s->hostname) ?></b> <span class="region"><?= $e($s->region) ?></span><?php endif ?>
                        <span class="mono"><?= $e($ip) ?></span>
                    </li>
                <?php endforeach ?>
            </ul>
        </section>

        <section class="panel">
            <?php $tableId = $card->domId() . '-ips' ?>
            <div class="panel-head">
                <h3>IPs of the scanner instances in the whole group <small><?= $a->isUnknown() ? '–' : $e(Html::number($ipCount)) ?></small></h3>
                <?php if ($ipCount > 0): ?>
                    <label class="ip-filter">
                        <input type="search" placeholder="Filter IP, hostname, status, ISC …" data-table="<?= $e($tableId) ?>" aria-label="Filter IPs">
                        <span class="filter-count" aria-live="polite"></span>
                    </label>
                <?php endif ?>
            </div>
            <?php if ($a->isUnknown()): ?>
                <p class="hint">IPs are not listed for the group "unknown" (too large).</p>
            <?php elseif ($ipCount === 0): ?>
                <p class="hint">No IPs in this window.</p>
            <?php else: ?>
                <div class="table-scroll">
                    <table class="instances" id="<?= $e($tableId) ?>">
                        <thead>
                        <tr>
                            <th>IP</th>
                            <th>PTR hostname</th>
                            <th title="Status of the PTR lookup">DNS</th>
                            <th title="Forward-confirmed reverse DNS: the hostname resolves back to this IP">FCrDNS</th>
                            <th>ISC list</th>
                            <th>First seen</th>
                            <th>Last seen</th>
                            <th class="num" title="Days in the window on which this IP belonged to the group">Days</th>
                        </tr>
                        </thead>
                        <tbody>
                        <?php foreach ($a->instances as $i): ?>
                            <tr>
                                <td class="mono"><?= $e($i->ip) ?></td>
                                <td class="mono host"><?= $i->hostname === null ? '<span class="none">–</span>' : $e($i->hostname) ?></td>
                                <td><span class="tag <?= $i->dnsStatus === 'NOERROR' ? '' : 'warn' ?>"><?= $e($i->dnsStatus) ?></span></td>
                                <td class="<?= $i->fcrdnsValid ? 'ok' : 'bad' ?>"><?= $i->fcrdnsValid ? '✓ valid' : '✗ invalid' ?></td>
                                <td><?= $i->iscId === null ? '<span class="none">–</span>' : '<span class="tag">' . $e($i->iscId) . '</span>' ?></td>
                                <td><?= $e($date($i->firstSeen)) ?></td>
                                <td><?= $e($date($i->lastSeen)) ?></td>
                                <td class="num" title="<?= $e($i->daysSeen) ?> of <?= $e($a->daysSeen) ?> days on which the group was seen">
                                    <span class="meter"><span style="width: <?= $pct($i->daysSeen, $a->daysSeen) ?>%"></span></span><?= $e($i->daysSeen) ?>
                                </td>
                            </tr>
                        <?php endforeach ?>
                        </tbody>
                    </table>
                </div>
                <p class="hint">Hostname, DNS status, FCrDNS and ISC list show the latest state in the window.</p>
            <?php endif ?>
        </section>
    </div>
</div>
