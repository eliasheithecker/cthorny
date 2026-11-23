<?php

declare(strict_types=1);

namespace Viewer\View;

use Viewer\Model\ProtocolResult;
use Viewer\Model\Window;
use Viewer\Model\WindowActor;

/** Eine Quartett-Karte: Anzeige-Daten einer Scanner-Gruppe in einem Fenster. */
final readonly class ActorCard
{
    public const ISC_TYPE = 'ISC';
    public const UNKNOWN_TYPE = 'Unknown';

    public const SORTS = [
        'score' => 'Interaction',
        'connections' => 'Connections',
        'ips' => 'IPs',
        'days' => 'Days seen',
        'name' => 'Name',
    ];

    /** @param array<string, string> $stats Kernwerte auf der Karte: Bezeichnung => Wert */
    public function __construct(
        public WindowActor $actor,
        public string $type,
        public array $stats,
        public float $totalScore,
    ) {
    }

    public static function fromActor(WindowActor $a, Window $w): self
    {
        $ipCount = $a->ipCount();

        return new self(
            actor: $a,
            type: $a->editorialType ?? ($a->isUnknown() ? self::UNKNOWN_TYPE : self::ISC_TYPE),
            stats: [
                // "unknown" listet keine IPs, 0 wäre irreführend
                'IPs observed' => $a->isUnknown() ? '–' : Html::number($ipCount),
                'FCrDNS valid' => Html::percent($a->fcrdnsValidCount(), $ipCount),
                'Connections' => Html::number($a->traffic->connectionsTotal),
                'Peak / sensor · 1 h' => Html::number($a->traffic->maxConnPerSensor1h),
                'Days seen' => sprintf('%d / %d', $a->daysSeen, $w->coverage->daysIncluded),
            ],
            totalScore: array_sum(array_map(fn (ProtocolResult $p) => $p->score, $a->protocols)),
        );
    }

    /** Eindeutige HTML-id für das Detail-Modal. */
    public function domId(): string
    {
        return 'actor-' . preg_replace('/[^A-Za-z0-9_-]+/', '-', $this->actor->idSource . '-' . $this->actor->id);
    }

    /** CSS-Klasse für die Farbe des Akteurstyps. */
    public function typeClass(): string
    {
        return self::classForType($this->type);
    }

    public static function classForType(string $type): string
    {
        return 'type-' . strtolower(preg_replace('/[^A-Za-z0-9]+/', '-', $type));
    }

    /**
     * @param list<self> $cards
     * @return list<self>
     */
    public static function sort(array $cards, string $by): array
    {
        $key = match ($by) {
            'connections' => fn (self $c) => $c->actor->traffic->connectionsTotal,
            'ips' => fn (self $c) => $c->actor->ipCount(),
            'days' => fn (self $c) => $c->actor->daysSeen,
            'name' => null,
            default => fn (self $c) => $c->totalScore,
        };
        usort($cards, fn (self $x, self $y) => $key === null
            ? strcasecmp($x->actor->id, $y->actor->id)
            : [$key($y), $x->actor->id] <=> [$key($x), $y->actor->id]);
        return $cards;
    }
}
