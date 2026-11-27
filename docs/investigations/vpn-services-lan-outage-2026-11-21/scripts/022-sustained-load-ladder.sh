#!/usr/bin/env bash
# Step 013 - progressive-size download ladder WITH concurrent loss/latency probing.
#
# READ-ONLY (ICMP + HTTPS downloads; nothing is written to the firewall or cluster).
#
# Why: on 2026-11-26 a 25 MB download achieved 288 Mbps while a 100 MB download stalled to
# 0 Mbps on the same link seconds apart. A link that works for small transfers and collapses
# for large ones is a capacity/queueing fault, not a routing fault, and it explains "everything
# is slow" better than packet loss alone does. Pinging the LAN side, the ISP's own gateway and
# two public resolvers *during* each transfer separates:
#   congestion at the ISP  -> latency and loss inflate only while pulling
#   a path/MTU problem     -> small transfers also degrade
#   a server-side limit    -> latency stays flat, only throughput dies
set -uo pipefail

BRAS=${BRAS:-210.186.239.254}
LAN=${LAN:-192.168.1.1}
SIZES=${SIZES:-"10000000 25000000 50000000 100000000 200000000"}
MAXTIME=${MAXTIME:-30}
ROUNDS=${ROUNDS:-2}

pingstat() { # host label  -> prints "label loss%/avgms" once stopped
  local host=$1 label=$2
  ping -t "$MAXTIME" -i 0.2 "$host" 2>/dev/null | python3 -c "
import sys
ls = sys.stdin.read().splitlines()
loss = next((x.split(',')[2].strip().split('%')[0] for x in ls if 'packet loss' in x), 'NA')
avg = next((x.split('/')[4] for x in ls if 'round-trip' in x), 'NA')
print('%s=%s%%/%sms' % ('$label', loss, ('%.0f' % float(avg)) if avg != 'NA' else 'NA'))
"
}

echo "now: $(date '+%Y-%m-%d %H:%M %Z')   each row: transfer + 3 concurrent ping runs (${MAXTIME}s window)"
echo "     ping format = loss%/avg_rtt"
echo "     complete?   = whether the whole file arrived before the ${MAXTIME}s cap"
echo
printf "%-12s %-6s %-11s %-11s %-9s %-14s %-14s %s\n" \
  "size" "round" "Mbps" "complete?" "LAN" "ISP-bras" "google" "cloudflare"

for sz in $SIZES; do
  for r in $(seq 1 "$ROUNDS"); do
    pingstat "$LAN"   lan > /tmp/_lan.$$   & P1=$!
    pingstat "$BRAS"  bras > /tmp/_bras.$$ & P2=$!
    pingstat 8.8.8.8  gg   > /tmp/_gg.$$   & P3=$!
    pingstat 1.1.1.1  gc   > /tmp/_gc.$$   & P4=$!
    sleep 1   # let the pings settle before load starts
    res=$(curl -o /dev/null -sL --max-time "$MAXTIME" -w '%{speed_download} %{size_download} %{http_code}' \
      "https://speed.cloudflare.com/__down?bytes=$sz" 2>/dev/null)
    wait "$P1" "$P2" "$P3" "$P4" 2>/dev/null
    got=$(echo "$res" | awk '{print $2}')
    mbps=$(echo "$res" | awk '{printf "%.0f", $1*8/1e6}')
    if [ -z "$got" ]; then mbps=${mbps:-0}; fi
    done_=$([ "${got:-0}" -ge $((sz - 1000)) ] && echo "yes" || echo "NO (${got:-0})")
    printf "%-12s %-6s %-11s %-11s %-9s %-14s %-14s %s\n" \
      "$sz" "$r" "${mbps:-0}" "$done_" "$(cat /tmp/_lan.$$)" "$(cat /tmp/_bras.$$)" \
      "$(cat /tmp/_gg.$$)" "$(cat /tmp/_gc.$$)"
  done
done
rm -f /tmp/_lan.$$ /tmp/_bras.$$ /tmp/_gg.$$ /tmp/_gc.$$

echo
echo "reference (this circuit's measured baseline earlier in this incident): 912 Mbps down / 521 up"
echo "healthy link: identical Mbps at every size, ISP-gateway RTT 1-5 ms in every row."
