import logging
from collections import defaultdict, deque
from pathlib import Path

from utils import Context
from models.paths import WorkingFiles

log = logging.getLogger(__name__)

# Timeout to consider a SYN half-open if no ACK arrives
FLOW_TIMEOUT = 90.0 
# Optional threshold: how many distinct (dst_ip, dst_port) must be hit to classify as scanner
MIN_TARGETS = 1

## detect SYNs that did not have a ACK followup within 90 seconds
## if they accur on a port that did have a handler deployed, that
## is considered a half open scan.
def identify_half_open_scanners(ctx: Context) -> None:
    output_events_file = ctx.workingPathOf(WorkingFiles.HALF_OPEN_EVENTS)
    
    output_scanners_file = ctx.workingPathOf(WorkingFiles.HALF_OPEN_SCANNERS)
    
    if not ctx.force_reload and output_events_file.exists() and output_scanners_file.exists():
        log.info("Half-open events and scanners already created, skipping step")
        return
    
    input_file = ctx.workingPathOf(WorkingFiles.TCP_HANDSHAKE_MIN)
    
    # flows: (src_ip, src_port, dst_ip, dst_port) -> deque of SYN timestamps
    flows = defaultdict(deque)
    # for optional scanner aggregation
    targets = defaultdict(set)

    def expire_old(current_time, out_file):
        """Expire SYNs older than FLOW_TIMEOUT and log as half-open events"""
        expired_flows = []
        for flow, syn_queue in flows.items():
            while syn_queue and current_time - syn_queue[0] > FLOW_TIMEOUT:
                ts = syn_queue.popleft()
                src, sport, dst, dport = flow
                out_file.write(f"{ts}\t{src}\t{sport}\t{dst}\t{dport}\n")
                targets[src].add((dst, dport))
            if not syn_queue:
                expired_flows.append(flow)

        for f in expired_flows:
            del flows[f]



    with open(input_file) as f, open(output_events_file, "w") as out:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) != 6:
                continue
            ts_str, src_ip, dst_ip, src_port, dst_port, flags_hex = parts
            
            try:
                ts = float(ts_str)
                flags = int(flags_hex, 16)
            except ValueError:
                continue


            SYN = flags & 0x02
            ACK = flags & 0x10

            flow = (src_ip, src_port, dst_ip, dst_port)

            # Expire old SYNs first
            expire_old(ts, out)

            # New SYN from scanner, add to pending queue
            if SYN and not ACK:
                flows[flow].append(ts)

            # ACK-only packet from scanner -> handshake complete -> remove pending SYN
            elif ACK and not SYN:  
                if flow in flows and flows[flow]:
                    flows[flow].popleft()

        # Flush any remaining pending SYNs as half-open
        for flow, syn_queue in flows.items():
            src_ip, src_port, dst_ip, dst_port = flow
            for ts in syn_queue:
                out.write(f"{ts}\t{src_ip}\t{src_port}\t{dst_ip}\t{dst_port}\n")
                targets[src_ip].add((dst_ip, dst_port))

    print("Half-open event extraction complete.")

    scanners = [src_ip for src_ip, dsts in targets.items() if len(dsts) >= MIN_TARGETS]
    with open(output_scanners_file, "w") as f:
        for ip in sorted(scanners):
            f.write(ip + "\n")

    print(f"{len(scanners)} half-open scanners identified.")
    