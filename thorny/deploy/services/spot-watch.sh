#!/bin/bash
# Polls the EC2 metadata service for a spot interruption notice. AWS announces the
# interruption about 2 minutes in advance; then teardown.sh uploads everything.
# /latest/meta-data/spot/instance-action returns 404 normally and 200 once scheduled.
SCRIPT_DIR=${SCRIPT_DIR:-/var/scripts}
. "$SCRIPT_DIR/lib.sh"

POLL_SECONDS=${POLL_SECONDS:-5}

log "spot-watch: polling $IMDS_URL every $POLL_SECONDS s"
while true; do
    if notice=$(imds_get meta-data/spot/instance-action); then
        log "spot-watch: interruption notice: $notice"
        "$SCRIPT_DIR/teardown.sh"
        exit 0
    fi
    sleep "$POLL_SECONDS"
done
