#!/usr/bin/env bash
# Step 015 - sustained loss/latency recorder: produces evidence a call-centre cannot argue with.
#
# READ-ONLY (ICMP + HTTPS GET only). Run this DURING the ISP call and read the table aloud.
# Each round does: 10 ICMP probes to the ISP gateway, 10 to a public resolver, and a small
# real download, so loss, latency and application throughput are timestamped together.
#
#   SAMPLES=10 INTERVAL=15 ./015-loss-recorder.sh
set -uo pipefail
BRAS=${BRAS:-210.186.239.254}
PUB1=${PUB1:-8.8.8.8}
PUB2=${PUB2:-1.1.1.1}
LAN=${LAN:-192.168.1.1}
SAMPLES=${SAMPLES:-10}
INTERVAL=${INTERVAL:-15}
CSV=${CSV:-loss-recorder.csv}

probe(){ # host -> "loss% avg_ms"
  ping -c 10 -i 0.5 -t 3 "$1" 2>/dev/null | python3 -c "
import sys
ls=sys.stdin.read().splitlines()
l=[x.split(',')[2].strip().split('%')[0] for x in ls if 'packet loss' in x]
r=[x.split('/')[4] for x in ls if 'round-trip' in x]
print('%s,%s' % (l[0] if l else 'NA', ('%.1f'%float(r[0])) if r else 'NA'))
"
}
dl(){ # -> Mbps achieved in <=6 s, 0 if it stalled
  curl -o /dev/null -s --max-time 6 -w '%{speed_download}' \
    "https://speed.cloudflare.com/__down?bytes=8000000" 2>/dev/null \
    | python3 -c "
import sys
try: print('%.1f' % (float(sys.stdin.read().strip())*8/1e6))
except ValueError: print('STALL')
"
}

echo "utc_time,local_time,lan_loss%,lan_ms,bras_loss%,bras_ms,g888_loss%,g888_ms,g1111_loss%,g1111_ms,dl_mbps" > "$CSV"
echo "recording $SAMPLES rounds, ${INTERVAL}s apart -> $CSV"
printf "%-9s %-7s %-7s %-7s %-8s %-7s %-8s %-7s %-8s %-7s %s\n" TIME TZ "LAN%" "LANms" "BRAS%" "BRASms" "8.8%" "8.8ms" "1.1%" "1.1ms" "DL Mbps"

for i in $(seq 1 "$SAMPLES"); do
  a=$(probe "$LAN"); b=$(probe "$BRAS"); c=$(probe "$PUB1"); d=$(probe "$PUB2"); s=$(dl)
  echo "$(date -u '+%H:%M:%S'),$(date '+%H:%M'),$a,$b,$c,$d,$s" >> "$CSV"
  printf "%-9s %-7s %-7s %-7s %-8s %-7s %-8s %-7s %-8s %-7s %s\n" \
    "$(date -u '+%H:%M:%S')" "$(date '+%H:%M')" ${a//,/ } ${b//,/ } ${c//,/ } ${d//,/ } "$s"
  [ "$i" -lt "$SAMPLES" ] && sleep "$INTERVAL"
done

python3 - "$CSV" <<'PY'
import csv, sys
rows=list(csv.DictReader(open(sys.argv[1])))
def stats(k):
    v=[float(r[k]) for r in rows if r[k] not in ('NA','STALL','')]
    return (min(v), sum(v)/len(v), max(v)) if v else None
print("\n--- summary over %d rounds ---" % len(rows))
for label,k in (("LAN loss %","lan_loss%"),("BRAS loss %","bras_loss%"),("8.8.8.8 loss %","g888_loss%"),
                ("1.1.1.1 loss %","g1111_loss%"),("BRAS ms","bras_ms"),("8.8.8.8 ms","g888_ms"),
                ("download Mbps","dl_mbps")):
    s=stats(k)
    print("  %-16s min=%.1f  avg=%.1f  max=%.1f" % ((label,)+s) if s else "  %-16s no data" % label)
stalls=sum(1 for r in rows if r['dl_mbps']=='STALL')
print("  stalled downloads: %d of %d" % (stalls, len(rows)))
print("\n  read this to the ISP: your gateway address shows the same loss as the public")
print("  internet, while my LAN side is clean - the fault is upstream of my router.")
PY
