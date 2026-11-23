<?php

declare(strict_types=1);

namespace Viewer\Model;

/** Interaktionstiefe eines Scanners auf einem Protokoll. */
final readonly class ProtocolResult
{
    public function __construct(
        public int $maxTransportLevel,
        public float $maxApplicationLevel, // float wegen SmtpLevel.VRFY_EXPN = 2.5
        public float $score, // 0 bis 1
    ) {
    }

    public static function fromArray(array $data): self
    {
        return new self(
            maxTransportLevel: (int) $data['max_transport_level'],
            maxApplicationLevel: (float) $data['max_application_level'],
            score: (float) $data['score'],
        );
    }
}
