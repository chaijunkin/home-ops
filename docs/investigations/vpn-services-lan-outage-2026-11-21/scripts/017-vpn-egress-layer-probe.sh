#!/usr/bin/env bash
# Step 017 - which layer does the VPN egress actually break at? Probed, not assumed.
#
# READ-ONLY. The ISP path is healthy again (hop 2 = 13 ms, 0 % loss) but VpnProbeFailed is still
# firing, so the fault is isolated to the exit path itself. blackbox exposes an on-demand prober
# endpoint; the vpn prober pod lives on 10.10.31.20 (VLAN 31 macvlan), so every probe below
# travels the exact path the alert cares about:
#   pod -> vlan0.31.1 -> pf policy route -> wg2 (Proton) -> internet
# Targets are ordered from "inside the tunnel" to "outside it", so the first failing row is the
# layer that needs fixing.
set -uo pipefail
NAMESPACE=observability
SVC=blackbox-exporter-vpn
PORT=19115

kubectl -n "$NAMESPACE" port-forward "svc/$SVC" "$PORT:9115" >/dev/null 2>&1 &
PF=$!; trap 'kill $PF 2>/dev/null' EXIT; sleep 4

probe(){ # module target  -> one line verdict
  local m=$1 t=$2 out
  out=$(curl -s --max-time 20 "http://localhost:$PORT/probe?target=${t}&module=${m}&debug=true" 2>&1)
  echo "$out" | python3 -c "
import sys,re
s=sys.stdin.read()
ok=re.search(r'^probe_success (\S+)', s, re.M)
ip=re.search(r'^probe_ip_addr (\S+)', s, re.M)
err=re.search(r'discovered labels:.*?failure_reason=\"([^\"]+)\"', s, re.S) or re.search(r'failure_reason=\"([^\"]+)\"', s)
dur=re.search(r'^probe_duration_seconds (\S+)', s, re.M)
print('  %-12s %-28s %-8s %-16s %s%s' % ('$m','$t'[:28],
      {'1':'OK','0':'FAIL','None':'ERR?'}.get(ok.group(1) if ok else '', 'NO-REPLY'),
      (ip.group(1) if ip else '-'),
      ('%.0f ms'%(float(dur.group(1))*1000)) if dur else '-',
      (' | '+(err.group(1)[:60] if err else ''))))
"
}

echo "now $(date '+%H:%M %Z')  -  probes originate from 10.10.31.20 (VLAN 31 / Proton exit)"
echo
echo "=== layer 1: the tunnel's own other end (dpinger already says 13 ms / 0 % loss) ==="
probe icmp 10.2.0.1

echo
echo "=== layer 2: raw public IPs - no DNS, no TLS, just forwarding + reply ==="
for t in 1.1.1.1 8.8.8.8 9.9.9.9 208.67.222.222; do probe icmp "$t"; done

echo
echo "=== layer 3: TCP to a public port (does SYN-ACK come back?) ==="
for t in 1.1.1.1:53 1.1.1.1:443 8.8.8.8:443; do probe tcp_connect "$t"; done

echo
echo "=== layer 4: HTTPS by IP vs by name (separates egress from DNS) ==="
probe http_2xx "https://1.1.1.1"
probe http_2xx "https://one.one.one.one"

echo
echo "=== layer 5: what the prober pod can see about itself ==="
kubectl -n "$NAMESPACE" exec deploy/blackbox-exporter-vpn -- sh -c \
  'cat /etc/resolv.conf 2>/dev/null | head -4; ip route 2>/dev/null | head -6; ip addr show 2>/dev/null | grep -E "inet " | head -5' 2>&1 | sed 's/^/  /'

echo
echo "=== and the OPNsense service alert: which service is actually stopped? ==="
kubectl -n "$NAMESPACE" port-forward pod/prometheus-kube-prometheus-stack-0 19090:9090 >/dev/null 2>&1 &
PF2=$!; trap 'kill $PF $PF2 2>/dev/null' EXIT; sleep 4
for m in opnsense_services_stopped_total opnsense_services_total; do
  printf "  %-32s " "$m"
  curl -sG --max-time 20 "http://localhost:19090/api/v1/query" --data-urlencode "query=$m" | python3 -c "
import json,sys
rs=json.load(sys.stdin).get('data',{}).get('result',[])
print(rs[0]['value'][1] if rs else '(no series)')"
done
curl -sG --max-time 20 "http://localhost:19090/api/v1/query" --data-urlencode \
  'query=ALERTS{alertname=~"VpnProbeFailed|OpnsenseServiceStopped|BlackboxProbeFailed"}' | python3 -c "
import json,sys
for r in json.load(sys.stdin).get('data',{}).get('result',[]):
    m = r['metric']
    print('  ALERT %-24s state=%-8s target=%s' % (m.get('alertname'), m.get('state'), m.get('instance')))
" 2>/dev/null
