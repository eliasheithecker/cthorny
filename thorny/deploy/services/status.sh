#!/bin/bash
# Webhook /hooks/status: JSON with the sensor state. Based on CAIDA status.sh.
SCRIPT_DIR=${SCRIPT_DIR:-/var/scripts}
. "$SCRIPT_DIR/lib.sh"

SERVICES=("ssh.service" "ssh.socket" "webhook.socket" "gotrace.service" "thorny.service" "spot-watch.service")

status=$(jq -n --arg hostname "$(cat /etc/hostname)" --arg ipv4 "$(cfg ip4)" --arg ipv6 "$(cfg ip6)" \
    --arg teardown "$(cfg teardownState)" --arg start "$(cfg start)" --arg provider "$(cfg provider)" \
    --arg region "$(cfg region)" \
    '{hostname: $hostname, ipv4: $ipv4, ipv6: $ipv6, teardown: $teardown, start: $start, provider: $provider, region: $region}')
for s in "${SERVICES[@]}"; do
    status=$(echo "$status" | jq --arg k "$s" --arg v "$(systemctl is-active "$s")" '. + {($k): $v}')
done
echo "$status" | jq -c .
