#!/bin/bash
# Shared helpers for startup.sh, upload.sh, rewrite.sh, teardown.sh and spot-watch.sh.
# Installed to /var/scripts/lib.sh and sourced, never executed directly.
# All paths can be overridden via environment variables.

CONFIG_DIR=${CONFIG_DIR:-/root/config}
SCRIPT_DIR=${SCRIPT_DIR:-/var/scripts}
SPOOL_GOTRACE=${SPOOL_GOTRACE:-/var/spool/gotrace}
SPOOL_THORNY=${SPOOL_THORNY:-/var/spool/thorny}
LOCK_FILE=${LOCK_FILE:-/run/cthorny-upload.lock}
IMDS_URL=${IMDS_URL:-http://169.254.169.254}

# cron runs jobs with PATH=/usr/bin:/bin, but aws is in /usr/local/bin and ip in /usr/sbin.
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH

# AWS CLI settings of this sensor (endpoint, region, keys), written by startup.sh.
# Without a credentials file the CLI falls back to an IAM instance profile.
export AWS_CONFIG_FILE=${AWS_CONFIG_FILE:-$CONFIG_DIR/aws/config}
export AWS_SHARED_CREDENTIALS_FILE=${AWS_SHARED_CREDENTIALS_FILE:-$CONFIG_DIR/aws/credentials}

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }

# cfg <name>: value stored in $CONFIG_DIR/<name>.txt
cfg() { cat "$CONFIG_DIR/$1.txt" 2>/dev/null; }

# Length of a data window in seconds (gotrace split_time == thorny rotateMinutes).
window_seconds() { echo $(( $(cfg window_minutes || echo 10) * 60 )); }

# s3 <subcommand> <args...>: "aws s3" with the settings above, errors only.
s3() { local sub=$1; shift; aws s3 "$sub" --only-show-errors "$@"; }

# s3_cat <s3://...>: object content on stdout, non-zero if it does not exist.
s3_cat() { aws s3 cp --only-show-errors "$1" - 2>/dev/null; }

# s3://<bucket>/provider=<p>/region=<r>/ip=<a-b-c-d>
s3_prefix() {
    echo "s3://$(cfg bucket)/provider=$(cfg provider)/region=$(cfg region)/ip=$(cfg ip4 | tr . -)"
}

# Lifecycle folder of this boot: <s3_prefix>/<unix start>
lifecycle_prefix() { echo "$(s3_prefix)/$(cfg start)"; }

# partition_path <unix>: year=YYYY/month=MM/day=DD/hour=HH (UTC)
partition_path() { date -u -d "@$1" +"year=%Y/month=%m/day=%d/hour=%H"; }

# file_ts <path>: the <unix> of packets-<unix>.pcap.gz / thorny-<unix>.jsonl[.gz]
file_ts() {
    local name=${1##*/}
    name=${name#*-}
    name=${name%%.*}
    [[ $name =~ ^[0-9]+$ ]] || return 1
    echo "$name"
}

# window_closed <unix>: true if nobody writes into the window starting at <unix>
# any more. With FINAL=1 (teardown, services already stopped) everything counts as closed.
window_closed() {
    [ "${FINAL:-0}" = 1 ] && return 0
    [ $(( $1 + $(window_seconds) )) -le "$(date +%s)" ]
}

# imds_get <path>: GET from the EC2 instance metadata service (IMDSv2 with fallback to v1).
# Prints the body and returns non-zero on HTTP errors.
imds_get() {
    local token
    token=$(curl -sf -m 2 -X PUT "$IMDS_URL/latest/api/token" \
        -H "X-aws-ec2-metadata-token-ttl-seconds: 300" 2>/dev/null)
    if [ -n "$token" ]; then
        curl -sf -m 2 -H "X-aws-ec2-metadata-token: $token" "$IMDS_URL/latest/$1"
    else
        curl -sf -m 2 "$IMDS_URL/latest/$1"
    fi
}

# start_service <name>: enable and (re)start a systemd unit.
start_service() {
    systemctl enable "$1"
    systemctl restart "$1"
}

# stop_service <name>: SIGTERM, SIGKILL after 20 s. Returns when the process is gone,
# so its last file is complete.
stop_service() {
    timeout 20 systemctl stop "$1" || systemctl kill --signal=KILL "$1"
}
