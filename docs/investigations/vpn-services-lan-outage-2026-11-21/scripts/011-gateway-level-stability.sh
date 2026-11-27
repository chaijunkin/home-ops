#!/usr/bin/env bash
# Step 011 - "why is my speed unstable?" measured at the gateway boundary.
#
# READ-ONLY. Separates four things that all feel like "unstable internet":
#   1. the access link itself (PPPoE reconnects, interface errors)
#   2. the ISP's side of the wire (RTT/loss to the BRAS 210.186.239.254)
#   3. the firewall itself (states, mbuf, CPU, thermals)
#   4. inside the house (Wi-Fi vs wired, and our own load)
set -uo pipefail
NAMESPACE=observability
PROM_POD=prometheus-kube-prometheus-stack-0
PORT=19090
ISP_GW=210.186.239.254
FW=192.168.1.1

kubectl -n "$NAMESPACE" port-forward "pod/$PROM_POD" "$PORT:9090" >/dev/null 2>&1 &
PF=$!; trap 'kill $PF 2>/dev/null' EXIT; sleep 5
R(){ curl -sG --max-time 30 "http://localhost:$PORT/api/v1/query" --data-urlencode "query=$1" \
     | python3 -c "
import json,sys
rs=json.load(sys.stdin).get('data',{}).get('result',[])
print('     (no series)') if not rs else [print('     %-46s %s' % (str({k:v for k,v in r['metric'].items() if k in ('device','name','mode','peer','cpu')})[:46], r['value'][1])) for r in rs[:10]]
"; }
RANGE(){ # metric  window  step  hours  divisor
  curl -sG --max-time 45 "http://localhost:$PORT/api/v1/query_range" \
    --data-urlencode "query=$1" --data-urlencode "start=$(( $(date +%s) - ${4:-24}*3600 ))" \
    --data-urlencode "end=$(date +%s)" --data-urlencode "step=$2" | python3 -c "
import json,sys,time,statistics
d=float('${5:-1}')
rs=json.load(sys.stdin).get('data',{}).get('result',[])
print('     (no series)') if not rs else [print('   %s [pts=%d]' % (r['metric'].get('instance') or r['metric'].get('name') or '?', len(r['values']))) or print('     ', ' '.join('%s:%.0f'%(time.strftime('%Hh',time.gmtime(int(float(t)))), float(v)/d) for t,v in r['values'])) for r in rs]
"; }

echo "=== 1. hourly speed profile, last 24 h (the instability, quantified) ==="
for spec in 'last_over_time(speedtest_download_bits_per_second[2h])|3600|24|1000000|DOWN Mbps' \
            'last_over_time(speedtest_upload_bits_per_second[2h])|3600|24|1000000|UP Mbps' \
            'last_over_time(speedtest_ping_latency_milliseconds[2h])|3600|24|1|PING ms' \
            'last_over_time(speedtest_jitter_latency_milliseconds[2h])|3600|24|1|JITTER ms' \
            'last_over_time(speedtest_server_id[2h])|3600|24|1|SERVER id'; do
  IFS='|' read -r q st hr dv label <<< "$spec"
  echo "-- $label"; RANGE "$q" "$st" "$hr" "$dv"
done

echo
echo "=== 2. did the WAN link itself drop? (a negative 10-min delta = counter reset = reconnect) ==="
echo "-- pppoe0 receive, min 10-min delta over 24 h (negative => PPPoE re-established)"
RANGE 'delta(node_network_receive_bytes_total{instance=~"gateway.*",device="pppoe0"}[10m])' 600 24 1000000 "MB"
echo "-- interface errors reported by OPNsense itself"
R 'increase(opnsense_interfaces_input_errors_total[6h])'
R 'increase(opnsense_interfaces_output_errors_total[6h])'

echo
echo "=== 3. the firewall's own capacity, peak over 24 h (would it be the bottleneck?) ==="
R 'max_over_time(opnsense_pf_states_current[24h])'
R 'opnsense_pf_states_limit'
R 'max_over_time(opnsense_mbuf_clusters_current[24h])'
R 'opnsense_mbuf_clusters_limit'
R 'max_over_time(opnsense_temperature_celsius[24h])'
R 'max_over_time(1 - avg(rate(node_cpu_seconds_total{instance=~"gateway.*",mode="idle"}[5m]))[24h:1m])'

echo
echo "=== 4. dpinger: the only gateway that is monitored, last 24 h ==="
RANGE 'opnsense_gateways_rtt_milliseconds' 1800 24 1 'RTT ms'
RANGE 'opnsense_gateways_loss_percentage'  1800 24 1 'LOSS %'
RANGE 'opnsense_gateways_status'           1800 24 1 'STATUS'

echo
echo "=== 5. is telemetry continuous? (a gap here fakes 'instability') ==="
R 'time() - timestamp(opnsense_up)'
R 'time() - timestamp(up{instance=~"gateway.*"} or vector(99999))'
R 'count_over_time(opnsense_up[6h])'

echo
echo "=== 6. live latency ladder from this Mac: LAN -> firewall -> ISP BRAS -> internet ==="
for h in "$FW" "$ISP_GW" 8.8.8.8 1.1.1.1; do
  printf "   %-17s " "$h"
  ping -c 20 -i 0.3 -t 4 "$h" 2>/dev/null | tail -1 | sed 's/.*= //' || echo "no reply"
done
echo "   (20 probes each; look at loss and max, not just the average)"
