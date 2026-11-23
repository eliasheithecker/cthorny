#!/bin/bash
# Ends the current lifecycle: stop capturing, upload everything, write termination.txt.
# Triggered by spot-watch.sh (spot interruption notice, ~2 min before termination)
# or by the webhook (GET /hooks/teardown?token=...). Runs at most once per lifecycle.
#
# termination.txt (uploaded last to <lifecycle>/termination.txt):
#   listen_end=<unix>       thorny and gotrace stopped, nothing is captured any more
#   termination_end=<unix>  final upload finished
SCRIPT_DIR=${SCRIPT_DIR:-/var/scripts}
. "$SCRIPT_DIR/lib.sh"

exec 8>"$CONFIG_DIR/teardown.lock"
flock -n 8 || { log "teardown already running"; exit 0; }
[ "$(cfg teardownState)" = finished ] && { log "teardown already finished"; exit 0; }

log "teardown started"
echo "started" > "$CONFIG_DIR/teardownState.txt"

stop_service thorny
stop_service gotrace
listen_end=$(date +%s)

FINAL=1 "$SCRIPT_DIR/upload.sh"

termination_end=$(date +%s)
printf 'listen_end=%s\ntermination_end=%s\n' "$listen_end" "$termination_end" > "$CONFIG_DIR/termination.txt"
s3 cp "$CONFIG_DIR/termination.txt" "$(lifecycle_prefix)/termination.txt"

echo "finished" > "$CONFIG_DIR/teardownState.txt"
log "teardown finished in $((termination_end - listen_end)) s after listen_end"
