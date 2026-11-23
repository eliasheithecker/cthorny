#!/bin/bash
# Uploads all closed data windows to S3 and deletes them locally.
#   cron: 1-59/10 * * * *   (one minute after every rotation)
#   FINAL=1 upload.sh       (teardown, after thorny/gotrace were stopped: uploads everything)
#
# packets-<unix>.pcap.gz  -> <s3_prefix>/year=/month=/day=/hour=/packets-<unix>.pcap.gz
# thorny-<unix>.jsonl     -> <s3_prefix>/year=/month=/day=/hour=/thorny-<unix>.jsonl.gz
# every partition touched -> descriptor-link.txt with the lifecycle start(s)
# See deploy/README.md.
SCRIPT_DIR=${SCRIPT_DIR:-/var/scripts}
. "$SCRIPT_DIR/lib.sh"

# One upload at a time (cron vs. teardown)
exec 9>"$LOCK_FILE"
if ! flock -w 90 9; then
    log "upload: lock $LOCK_FILE busy for 90 s, giving up"
    exit 1
fi

prefix=$(s3_prefix)
declare -A touched=()   # partitions that received a file in this run
uploaded=0
failed=0

# Pcaps of these providers carry the private IP as destination and are rewritten.
needs_rewrite=0
case "$(cfg provider)" in aws|gcp|azure|terraform|tencent) needs_rewrite=1 ;; esac

upload_window_file() { # <file> <unix>
    local part
    part=$(partition_path "$2")
    if s3 cp "$1" "$prefix/$part/"; then
        rm -f "$1"
        touched[$part]=1
        uploaded=$((uploaded + 1))
    else
        log "upload failed: $1 (kept for the next run)"
        failed=$((failed + 1))
    fi
}

# ---- pcaps (gotrace)
if [ -d "$SPOOL_GOTRACE" ]; then
    if [ "${FINAL:-0}" = 1 ]; then
        # in case gotrace left an uncompressed file behind when it was stopped
        for f in "$SPOOL_GOTRACE"/packets-*.pcap; do [ -e "$f" ] && gzip -f "$f"; done
    fi
    for f in "$SPOOL_GOTRACE"/packets-*.pcap.gz; do
        [ -e "$f" ] || continue
        ts=$(file_ts "$f") || continue
        window_closed "$ts" || continue
        [ "$needs_rewrite" = 1 ] && "$SCRIPT_DIR/rewrite.sh" "$f"
        upload_window_file "$f" "$ts"
    done
fi

# ---- thorny logs
if [ -d "$SPOOL_THORNY" ]; then
    for f in "$SPOOL_THORNY"/thorny-*.jsonl; do
        [ -e "$f" ] || continue
        ts=$(file_ts "$f") || continue
        window_closed "$ts" || continue
        gzip -f "$f"
    done
    # also picks up .gz files from earlier failed uploads
    for f in "$SPOOL_THORNY"/thorny-*.jsonl.gz; do
        [ -e "$f" ] || continue
        ts=$(file_ts "$f") || continue
        upload_window_file "$f" "$ts"
    done
fi

# ---- descriptor-link.txt: once per partition and lifecycle
start=$(cfg start)
mkdir -p "$CONFIG_DIR/linked"
for part in "${!touched[@]}"; do
    marker="$CONFIG_DIR/linked/${part//\//_}"
    [ -e "$marker" ] && continue
    remote="$prefix/$part/descriptor-link.txt"
    # Normally one line. If two lifecycles of the same IP share an hour (e.g. reboot), keep both.
    { s3_cat "$remote"; echo "$start"; } | grep -E '^[0-9]+$' | sort -un > "$CONFIG_DIR/descriptor-link.tmp"
    if s3 cp "$CONFIG_DIR/descriptor-link.tmp" "$remote"; then
        touch "$marker"
    else
        log "upload failed: $remote"
        failed=$((failed + 1))
    fi
done
rm -f "$CONFIG_DIR/descriptor-link.tmp"
find "$CONFIG_DIR/linked" -type f -mtime +1 -delete 2>/dev/null

log "upload done: $uploaded files, ${#touched[@]} partitions, $failed failures (FINAL=${FINAL:-0})"
[ "$failed" = 0 ]
