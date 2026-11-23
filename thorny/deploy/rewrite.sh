#!/bin/bash
# rewrite.sh <packets-<unix>.pcap.gz>
# On NATed clouds (AWS, GCP, ...) gotrace sees the private IP of the instance.
# Rewrites it to the public IPv4 in place. Called by upload.sh per closed pcap.
# Based on CAIDA cloudtelescope-public scripts/services/rewrite.sh.
SCRIPT_DIR=${SCRIPT_DIR:-/var/scripts}
. "$SCRIPT_DIR/lib.sh"

file=$1
[ -f "$file" ] || { echo "usage: $0 <pcap.gz>" >&2; exit 1; }

ip=$(cfg ip4)
iface=$(ip route show default | awk '{print $5; exit}')
localip=$(ip -4 addr show dev "$iface" | awk '/inet /{print $2}' | cut -d/ -f1 | head -n 1)

if [ -z "$ip" ] || [ -z "$localip" ] || [ "$ip" = "$localip" ]; then
    exit 0
fi

# thorny answers, so the capture also holds outgoing packets: rewrite source and destination.
if zcat "$file" | tcprewrite --srcipmap="$localip/32:$ip/32" --dstipmap="$localip/32:$ip/32" \
        --infile=- --outfile=- | gzip > "$file.rewrite"; then
    mv "$file.rewrite" "$file"
else
    log "rewrite failed for $file, uploading unmodified"
    rm -f "$file.rewrite"
fi
