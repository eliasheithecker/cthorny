<?php

declare(strict_types=1);

namespace Viewer\Model;

/**
 * Verbindungs-Kennzahlen einer Scanner-Gruppe (DailyTraffic in daily.py).
 * maxConnPerSensor*: alle IPs der Gruppe zusammen; maxConnPerInstancePerSensor*: eine einzelne IP der Gruppe.
 * Im Fenster: *Day = höchster Wert an einem einzelnen Tag, *1h = höchster Wert in einem 60-Minuten-Fenster.
 */
final readonly class Traffic
{
    /** @param list<string> $sensorsHit */
    public function __construct(
        public array $sensorsHit,
        public int $connectionsTotal,
        public int $connectionsFull,
        public int $connectionsHalfOpen,
        public int $maxConnPerSensorPortDay,
        public int $maxConnPerSensorPort1h,
        public int $maxConnPerSensorDay,
        public int $maxConnPerSensor1h,
        public int $maxConnPerInstancePerSensorPortDay,
        public int $maxConnPerInstancePerSensorPort1h,
        public int $maxConnPerInstancePerSensorDay,
        public int $maxConnPerInstancePerSensor1h,
    ) {
    }

    public static function fromArray(array $data): self
    {
        return new self(
            sensorsHit: $data['sensors_hit'],
            connectionsTotal: (int) $data['connections_total'],
            connectionsFull: (int) $data['connections_full'],
            connectionsHalfOpen: (int) $data['connections_half_open'],
            maxConnPerSensorPortDay: (int) $data['max_conn_per_sensor_port_day'],
            maxConnPerSensorPort1h: (int) $data['max_conn_per_sensor_port_1h'],
            maxConnPerSensorDay: (int) $data['max_conn_per_sensor_day'],
            maxConnPerSensor1h: (int) $data['max_conn_per_sensor_1h'],
            maxConnPerInstancePerSensorPortDay: (int) $data['max_conn_per_scanner_instance_per_sensor_port_day'],
            maxConnPerInstancePerSensorPort1h: (int) $data['max_conn_per_scanner_instance_per_sensor_port_1h'],
            maxConnPerInstancePerSensorDay: (int) $data['max_conn_per_scanner_instance_per_sensor_day'],
            maxConnPerInstancePerSensor1h: (int) $data['max_conn_per_scanner_instance_per_sensor_1h'],
        );
    }
}
