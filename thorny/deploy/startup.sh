#!/bin/bash
# Bootstraps a cthorny sensor (thorny + gotrace). Called by cloud-init (userData.sh.tpl) on every boot:
#   startup.sh <bucket> <s3-endpoint> <s3-access-key> <s3-secret-key> <webhook-pw> <provider> <region>
# Based on CAIDA cloudtelescope-public scripts/startup.sh. See deploy/README.md.
#
# Environment:
#   THORNY_VERSION      git tag of the release to deploy (e.g. thorny-v0.1.0). Scripts and binaries are fetched
#                       for exactly this tag. Required unless BASE_URL and THORNY_RELEASE_URL are both set.
#   BASE_URL            where the deploy scripts are fetched from (curl, file:// works)
#   THORNY_RELEASE_URL  where thorny-linux-<arch> and aws-config.yaml are fetched from
#   ROTATE_MINUTES      data window length (gotrace split_time and thorny rotateMinutes), default 10
#   PUBLIC_IP           skip public IPv4 detection and use this value
#   S3_REGION           region of the bucket, default us-east-1
set -o pipefail

REPO=eliasheithecker/cthorny
if [ -n "${THORNY_VERSION:-}" ]; then
    BASE_URL=${BASE_URL:-https://raw.githubusercontent.com/$REPO/$THORNY_VERSION/thorny/deploy}
    THORNY_RELEASE_URL=${THORNY_RELEASE_URL:-https://github.com/$REPO/releases/download/$THORNY_VERSION}
elif [ -z "${BASE_URL:-}" ] || [ -z "${THORNY_RELEASE_URL:-}" ]; then
    echo "THORNY_VERSION (or BASE_URL and THORNY_RELEASE_URL) must be set" >&2
    exit 1
fi
THORNY_VERSION=${THORNY_VERSION:-dev}   # local test with file:// URLs
ROTATE_MINUTES=${ROTATE_MINUTES:-10}
SSH_PORT=28763

if [ "$#" -ne 7 ]; then
    echo "usage: $0 <bucket> <s3-endpoint> <access-key> <secret-key> <webhook-pw> <provider> <region>" >&2
    exit 1
fi

fetch() { curl -fsSL --retry 3 "$1" -o "$2" || { echo "download failed: $1" >&2; return 1; }; }

# ---------------------------------------------------------------- packages + scripts
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y curl ca-certificates unzip openssl jq dnsutils iproute2 gzip tcpdump tcpreplay cron

mkdir -p /var/scripts
fetch "$BASE_URL/lib.sh" /var/scripts/lib.sh || exit 1
for s in upload.sh rewrite.sh services/teardown.sh services/spot-watch.sh services/ping.sh \
         services/status.sh services/restart.sh services/redeploy.sh; do
    fetch "$BASE_URL/$s" "/var/scripts/${s##*/}"
done
chmod +x /var/scripts/*
. /var/scripts/lib.sh

# ---------------------------------------------------------------- config of this lifecycle
mkdir -p "$CONFIG_DIR"
echo "$1" > "$CONFIG_DIR/bucket.txt"
echo "$2" > "$CONFIG_DIR/storageLoc.txt"
echo "$3" > "$CONFIG_DIR/storageAccKey.txt"
echo "$4" > "$CONFIG_DIR/storageSecKey.txt"
echo "$5" > "$CONFIG_DIR/webhookPw.txt"
echo "$6" > "$CONFIG_DIR/provider.txt"
echo "$7" > "$CONFIG_DIR/region.txt"
echo "$THORNY_VERSION" > "$CONFIG_DIR/version.txt"
echo "$ROTATE_MINUTES" > "$CONFIG_DIR/window_minutes.txt"
echo "available" > "$CONFIG_DIR/teardownState.txt"
start=$(date +%s)
echo "$start" > "$CONFIG_DIR/start.txt"
rm -rf "$CONFIG_DIR/linked" "$CONFIG_DIR/termination.txt"   # markers belong to the previous lifecycle
mkdir -p "$CONFIG_DIR/linked"
log "lifecycle start $start"

# Self-signed cert for the webhook server
openssl req -x509 -newkey ed25519 -keyout "$CONFIG_DIR/key.key" -outform PEM -out "$CONFIG_DIR/cert.pem" \
    -days 365 -nodes -subj "/C=DE/ST=NW/L=Muenster/O=Cloud Telescope/OU=Research/CN=$(cat /etc/hostname)"

ARCH=$(dpkg --print-architecture)   # amd64 | arm64
iface=$(ip route show default | awk '{print $5; exit}')

# ---------------------------------------------------------------- binaries
# AWS CLI v2 for all S3 transfers (MinIO no longer distributes the mc client).
if ! command -v aws >/dev/null; then
    fetch "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" /tmp/awscliv2.zip \
        && unzip -qo /tmp/awscliv2.zip -d /tmp && /tmp/aws/install --update
    rm -rf /tmp/awscliv2.zip /tmp/aws
fi

curl -fsSL "https://github.com/adnanh/webhook/releases/latest/download/webhook-linux-$ARCH.tar.gz" -o /tmp/webhook.tar.gz \
    && tar xf /tmp/webhook.tar.gz -C /tmp && mv "/tmp/webhook-linux-$ARCH/webhook" /usr/local/bin/webhook
rm -rf /tmp/webhook.tar.gz "/tmp/webhook-linux-$ARCH"

# gotrace is only built for amd64
mkdir -p /etc/gotrace "$SPOOL_GOTRACE"
if [ "$ARCH" = amd64 ]; then
    fetch "https://gitlab.git.nrw/nkempen/gotrace/-/jobs/artifacts/main/download?job=build" /tmp/gotrace.zip \
        && unzip -o /tmp/gotrace.zip -d /tmp/gotrace && install -m 755 /tmp/gotrace/gotrace /usr/local/bin/gotrace
    rm -rf /tmp/gotrace.zip /tmp/gotrace
    fetch https://gitlab.git.nrw/nkempen/gotrace/-/raw/main/config.yaml /etc/gotrace/config.yaml
    sed -i -e "s/##IFACE##/$iface/g" \
           -e "s|^split_time:.*|split_time: \"${ROTATE_MINUTES}m\"|" \
           -e "s|^outdir:.*|outdir: \"$SPOOL_GOTRACE\"|" /etc/gotrace/config.yaml
else
    log "WARNING: no gotrace build for $ARCH, pcap capture disabled"
fi

# ---------------------------------------------------------------- public IP
ip4=${PUBLIC_IP:-}
if [ -z "$ip4" ] && [ "$6" = aws ]; then
    ip4=$(imds_get meta-data/public-ipv4)
fi
if [ -z "$ip4" ]; then
    ip4=$(dig -4 +short +time=3 +tries=2 myip.opendns.com @resolver1.opendns.com)
fi
ip6=""
if [ "$6" = aws ]; then
    ip6=$(imds_get meta-data/ipv6)
fi
if [ -z "$ip6" ]; then
    # dig prints errors (";; ...") on stdout, keep only real addresses
    ip6=$(dig -6 +short +time=2 +tries=1 @resolver1.opendns.com myip.opendns.com ANY 2>/dev/null \
        | grep -E '^[0-9a-fA-F:]+$' | head -n 1)
fi
echo "$ip4" > "$CONFIG_DIR/ip4.txt"
echo "$ip6" > "$CONFIG_DIR/ip6.txt"
log "public ipv4=$ip4 ipv6=$ip6"
if [ -z "$ip4" ]; then
    echo "could not determine public IPv4, aborting" >&2
    exit 1
fi

# ---------------------------------------------------------------- thorny
mkdir -p /etc/thorny "$SPOOL_THORNY" "$CONFIG_DIR/thorny"
fetch "$THORNY_RELEASE_URL/thorny-linux-$ARCH" /usr/local/bin/thorny && chmod +x /usr/local/bin/thorny
fetch "$THORNY_RELEASE_URL/aws-config.yaml" /etc/thorny/config.yaml
sed -i -e "s/##PUBLICIP##/$ip4/g" \
       -e "s|^\(  *rotateMinutes:\).*|\1 $ROTATE_MINUTES|" \
       -e "s|^\(  *logDir:\).*|\1 '$SPOOL_THORNY'|" /etc/thorny/config.yaml

# ---------------------------------------------------------------- systemd units
for u in thorny.service spot-watch.service webhook.service webhook.socket; do
    fetch "$BASE_URL/services/$u" "/usr/lib/systemd/system/$u"
done
[ -x /usr/local/bin/gotrace ] && fetch https://gitlab.git.nrw/nkempen/gotrace/-/raw/main/gotrace.service \
    /usr/lib/systemd/system/gotrace.service
fetch "$BASE_URL/services/webhook.json" /etc/webhook.json
sed -i "s/##WHPW##/$5/g" /etc/webhook.json

# ---------------------------------------------------------------- S3 + descriptor
# AWS CLI config: endpoint only for non-AWS S3 (path-style), keys only if given (else IAM role).
mkdir -p "$CONFIG_DIR/aws"
{
    echo "[default]"
    echo "region = ${S3_REGION:-us-east-1}"
    if [ -n "$2" ] && [[ "$2" != *amazonaws.com* ]]; then
        echo "endpoint_url = $2"
        printf 's3 =\n    addressing_style = path\n'
    fi
} > "$AWS_CONFIG_FILE"
rm -f "$AWS_SHARED_CREDENTIALS_FILE"
if [ -n "$3" ]; then
    printf '[default]\naws_access_key_id = %s\naws_secret_access_key = %s\n' "$3" "$4" > "$AWS_SHARED_CREDENTIALS_FILE"
    chmod 600 "$AWS_SHARED_CREDENTIALS_FILE"
fi

. /etc/os-release
jq -n --arg hostname "$(cat /etc/hostname)" --arg provider "$6" --arg ipv4 "$ip4" --arg ipv6 "$ip6" \
      --arg os "$(echo "$PRETTY_NAME" | tr -d ' ')" --arg region "$7" --arg version "$THORNY_VERSION" \
      '{hostname: $hostname, provider: $provider, ipv4: $ipv4, ipv6: $ipv6, os: $os, region: $region, version: $version}' \
      > "$CONFIG_DIR/descriptor.txt"
s3 cp "$CONFIG_DIR/descriptor.txt" "$(lifecycle_prefix)/descriptor.txt"

# ---------------------------------------------------------------- upload cron
# One minute after every rotation; needs 60 % ROTATE_MINUTES == 0 so the windows line up.
(crontab -l 2>/dev/null | grep -v /var/scripts/upload.sh; \
 echo "1-59/$ROTATE_MINUTES * * * * /var/scripts/upload.sh >> /var/log/cthorny-upload.log 2>&1") | crontab -

# ---------------------------------------------------------------- host config
# Real SSH moves to $SSH_PORT so thorny can listen on 22. Ubuntu 22.04 runs ssh.service
# (sshd_config.d), Ubuntu >= 22.10 uses socket activation (ssh.socket.d); set both.
mkdir -p /etc/ssh/sshd_config.d /etc/systemd/system/ssh.socket.d
echo "Port $SSH_PORT" > /etc/ssh/sshd_config.d/10-cthorny-port.conf
printf '[Socket]\nListenStream=\nListenStream=%s\n' "$SSH_PORT" > /etc/systemd/system/ssh.socket.d/listen.conf
systemctl daemon-reload
if systemctl is-enabled --quiet ssh.socket 2>/dev/null; then
    systemctl restart ssh.socket
else
    systemctl restart ssh
fi

# IPv6 resolver as in the original, plus an IPv4 one for v4-only networks
systemctl disable --now systemd-resolved
rm -f /etc/resolv.conf
printf 'nameserver 2001:4860:4860::8888\nnameserver 8.8.8.8\n' > /etc/resolv.conf

# thorny answers on 22/23/25/389, so the CAIDA "drop everything" iptables rules are gone.
[ "$6" = vultr ] && ufw disable

systemctl enable --now webhook.socket

# ---------------------------------------------------------------- start services
[ -x /usr/local/bin/gotrace ] && start_service gotrace
start_service thorny
start_service spot-watch

# ---------------------------------------------------------------- ssh/ + tls/ of this lifecycle
ssh_keys=(/root/config/thorny/ssh/id_ed25519 /root/config/thorny/ssh/id_rsa /root/config/thorny/ssh/id_ecdsa)
tls_files=(/root/config/thorny/tls/cert.pem /root/config/thorny/tls/key.pem)
for _ in $(seq 1 60); do
    missing=0
    for f in "${ssh_keys[@]}" "${tls_files[@]}"; do [ -s "$f" ] || missing=1; done
    [ "$missing" = 0 ] && break
    sleep 1
done
for f in "${ssh_keys[@]}"; do [ -s "$f" ] && s3 cp "$f" "$(lifecycle_prefix)/ssh/"; done
for f in "${tls_files[@]}"; do [ -s "$f" ] && s3 cp "$f" "$(lifecycle_prefix)/tls/"; done
[ "$missing" = 1 ] && log "WARNING: not all thorny ssh/tls files appeared within 60 s"

log "We are operational, lifecycle $(lifecycle_prefix)"
