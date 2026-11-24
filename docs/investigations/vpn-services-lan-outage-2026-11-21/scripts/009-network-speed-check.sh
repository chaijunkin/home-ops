#!/usr/bin/env bash
# Step 009 - "what is my internet speed, actually?" (READ-ONLY)
#
# Why this script exists: the first reading of this data was wrong twice.
#   1. speedtest_* looked like "no data at all" -> it is scraped every 60m, and
#      Prometheus' 5m lookback means an instant query returns nothing for ~55
#      minutes of every hour. Always use last_over_time(...[2h]).
#   2. A raw query_range on the metric name returns empty for the same reason
#      (steps miss the hourly samples). Subquery or nothing.
set -uo pipefail
NAMESPACE=observability
PROM_POD=prometheus-kube-prometheus-stack-0
LOCAL_PORT=19090

kubectl -n "$NAMESPACE" port-forward "pod/$PROM_POD" "$LOCAL_PORT:9090" >/dev/null 2>&1 &
PF=$!; trap 'kill $PF 2>/dev/null' EXIT; sleep 5
Q(){ curl -sG --max-time 40 "http://localhost:$LOCAL_PORT/api/v1/query_range" \
       --data-urlencode "query=$1" --data-urlencode "start=$(( $(date +%s) - ${2:-604800} ))" \
       --data-urlencode "end=$(date +%s)" --data-urlencode "step=${3:-3600}"; }
SUM(){ python3 -c "
import json,sys,time,statistics
div=float('$1')
rs=json.load(sys.stdin).get('data',{}).get('result',[])
if not rs: print('     (no data)')
for r in rs:
    vals=[(int(float(t)),float(v)) for t,v in r['values'] if float(v)>0]
    print('     instance=%s points=%d' % (r['metric'].get('instance'), len(vals)))
    if vals:
        n=[v/div for _,v in vals]
        print('       min %.1f | median %.1f | mean %.1f | max %.1f' % (min(n),statistics.median(n),sum(n)/len(n),max(n)))
        print('       last: %s = %.1f' % (time.strftime('%m-%d %Hh UTC',time.gmtime(vals[-1][0])), vals[-1][1]/div))
"; }

echo "=== 1. 7-day automated WAN history (hourly, cluster -> speedtest server) ==="
for spec in "speedtest_download_bits_per_second 1000000" "speedtest_upload_bits_per_second 1000000" "speedtest_ping_latency_milliseconds 1"; do
  set -- $spec; echo "-- $1"; Q "last_over_time($1[2h])" | SUM "$2"
done
echo "-- which test server did it use? (a changed server invalidates the trend)"
Q 'last_over_time(speedtest_server_id[2h])' | SUM 1

echo
echo "=== 2. live test right now (exporter runs a fresh test per request, ~60-90 s) ==="
kubectl get --raw "/api/v1/namespaces/$NAMESPACE/services/speedtest-exporter:9798/proxy/metrics" \
  | grep -E '^speedtest' | sed 's/^/  /'

echo
echo "=== 3. is the link carrying anything? (WAN pppoe0, Mbps) ==="
curl -sG --max-time 25 "http://localhost:$LOCAL_PORT/api/v1/query" \
  --data-urlencode 'query=rate(node_network_receive_bytes_total{instance=~"gateway.*",device="pppoe0"}[5m])*8/1e6' \
  | python3 -c "import json,sys;r=json.load(sys.stdin)['data']['result'];print('  in  %.1f Mbps'%float(r[0]['value'][1]) if r else '  (no data)')"
curl -sG --max-time 25 "http://localhost:$LOCAL_PORT/api/v1/query" \
  --data-urlencode 'query=rate(node_network_transmit_bytes_total{instance=~"gateway.*",device="pppoe0"}[5m])*8/1e6' \
  | python3 -c "import json,sys;r=json.load(sys.stdin)['data']['result'];print('  out %.1f Mbps'%float(r[0]['value'][1]) if r else '  (no data)')"

echo
echo "=== 4. this Mac, and how it connects (compare against 1-3) ==="
route -n get default 2>/dev/null | grep -E 'interface' | sed 's/^/  default via /'
system_profiler SPAirPortDataType 2>/dev/null | grep -iE 'PHY Mode: 802.11(ax|ac)$|Transmit Rate|Channel: .*MHz' | head -3 | sed 's/^/  /'
for h in 192.168.1.1 8.8.8.8 1.1.1.1; do printf "  %-14s " "$h"; ping -c 8 -t 5 "$h" 2>/dev/null | tail -1 | sed 's/.*= //'; done
echo "  full capacity test (Apple's server, multi-stream; run manually, ~30 s):"
echo "    /usr/bin/networkQuality -s"
