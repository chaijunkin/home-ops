#!/usr/bin/env bash
# Step 016 - state of the VPN probe vs state of the tunnel: what has to change to clear it.
#
# READ-ONLY. VpnProbeFailed is a *symptom* alert: probe_success{service="blackbox-exporter-vpn"}
# == 0 for 15m, where the prober pod is pinned to 10.10.31.20 on the VPN_SERVICES_LAN (VLAN 31)
# macvlan, so its traffic must traverse the OPNsense Proton exit to reach 1.1.1.1.
# Resolving the alert means restoring egress; the four checks below say which layer is broken.
set -uo pipefail
NAMESPACE=observability
PROM_POD=prometheus-kube-prometheus-stack-0
PORT=19090
HERE=$(cd "$(dirname "$0")" && pwd)
FMT="$HERE/lib-fmt.py"

kubectl -n "$NAMESPACE" port-forward "pod/$PROM_POD" "$PORT:9090" >/dev/null 2>&1 &
PF=$!; trap 'kill $PF 2>/dev/null' EXIT; sleep 5
q(){ curl -sG --max-time 30 "http://localhost:$PORT/api/v1/query" --data-urlencode "query=$1" | python3 "$FMT" instant; }
rng(){ curl -sG --max-time 45 "http://localhost:$PORT/api/v1/query_range" --data-urlencode "query=$1" \
   --data-urlencode "start=$(( $(date +%s) - ${2:-24}*3600 ))" --data-urlencode "end=$(date +%s)" \
   --data-urlencode "step=${3:-1800}" | python3 "$FMT" range; }

echo "now: $(date '+%Y-%m-%d %H:%M %Z')  /  $(date -u '+%H:%M UTC')"

echo
echo "=== 1. the alert itself: is it firing right now, and since when? ==="
q 'ALERTS{alertname=~"VpnProbeFailed|BlackboxProbeFailed|OpnsenseServiceStopped|OpnsenseFirewallUnreachable"}'
echo "-- probe_success for the vpn prober, last 48 h (0 = no egress through the tunnel)"
rng 'probe_success{service="blackbox-exporter-vpn"}' 48 1800

echo
echo "=== 2. LAYER CHECK A: is the WireGuard crypto session even alive? ==="
echo "-- which wireguard metrics does the exporter publish at all?"
curl -sG --max-time 30 "http://localhost:$PORT/api/v1/label/__name__/values" \
  --data-urlencode 'match[]=opnsense_wireguard.*' | python3 -c "
import json,sys
v=json.load(sys.stdin).get('data',[])
print('\n'.join('     '+x for x in v) or '     (none)')"

echo "-- peer counters, last 6 h (kB/s). ~0.5-0.7 kB/s RX = handshakes only, no user traffic"
rng 'rate(opnsense_wireguard_peer_received_bytes_total[15m])*8/1e3' 6 1800
rng 'rate(opnsense_wireguard_peer_transmitted_bytes_total[15m])*8/1e3' 6 1800

echo
echo "=== 3. LAYER CHECK B: is VLAN 31 moving anything? (healthy = ~5-6 kB/s symmetric) ==="
rng 'rate(node_network_receive_bytes_total{device="vlan0.31.1"}[15m])*8/1e3' 12 1800
rng 'rate(node_network_transmit_bytes_total{device="vlan0.31.1"}[15m])*8/1e3' 12 1800

echo
echo "=== 4. LAYER CHECK C: what does the firewall's gateway monitor say today? ==="
rng 'opnsense_gateways_rtt_milliseconds' 12 1800
rng 'opnsense_gateways_loss_percentage' 12 1800

echo
echo "=== 5. has the ISP path recovered? (hop-2 141 ms was the 25 Nov fault) ==="
for h in 192.168.1.1 210.186.239.254 8.8.8.8; do
  printf "   %-17s " "$h"
  ping -c 20 -i 0.4 -t 3 "$h" 2>/dev/null | python3 -c "
import sys
ls=sys.stdin.read().splitlines()
l=[x.split(',')[2].strip() for x in ls if 'packet loss' in x]
r=[x.split('=')[1].strip() for x in ls if 'round-trip' in x]
print((l[0] if l else 'no reply'),'|',(r[0] if r else '-'),'ms')"
done

echo
echo "=== 6. who is on VLAN 31 and what do they think? ==="
kubectl get pods -A -o json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
for i in d['items']:
    ann=i['metadata'].get('annotations',{}).get('k8s.v1.cni.cncf.io/networks','')
    if '10.10.31' in str(ann) or 'vpn' in str(ann):
        cs=i['status'].get('containerStatuses',[])
        ready=all(c.get('ready') for c in cs) if cs else False
        print('   %-34s %-12s ready=%s restarts=%s' % (
            i['metadata']['name'][:34], i['status'].get('phase','?'), ready,
            sum(c.get('restartCount',0) for c in cs)))
"
