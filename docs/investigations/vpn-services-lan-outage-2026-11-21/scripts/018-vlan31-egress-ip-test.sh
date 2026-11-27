#!/usr/bin/env bash
# Step 018 - definitive: what does VLAN 31's traffic actually look like on the wire, and does
# anything come back? Run under bash (the probes loop needs word splitting; zsh will not do it).
#
# READ-ONLY: blackbox on-demand probing + one HTTP GET from inside VLAN-31 pods.
#
# Why this exists: on 26 Nov the ISP path was healthy again (hop 2 = 13 ms, 0 % loss) yet
# VpnProbeFailed was still firing, and the on-demand probes disagreed with themselves -
# ICMP to 1.1.1.1 timed out while a *TCP* handshake to 1.1.1.1:443 succeeded in 13 ms. Those two
# cannot both describe a dead tunnel, so the egress IP has to be read directly.
set -uo pipefail
NAMESPACE=observability
D=${D:-/private/var/folders/v4/pl1b82_501zdp6rvz85d8f_c0000gn/T/opnsense-triage/bb}
mkdir -p "$D"

kubectl -n "$NAMESPACE" port-forward svc/blackbox-exporter-vpn 19115:9115 >/dev/null 2>&1 &
PF=$!
sleep 4

echo "=== A. on-demand probes from 10.10.31.20, with the real error text ==="
for spec in "icmp 1.1.1.1" "icmp 8.8.8.8" "tcp_connect 1.1.1.1:443" "tcp_connect 9.9.9.9:53" "http_2xx https://1.1.1.1" "http_2xx https://one.one.one.one" "http_2xx http://example.com/"; do
  set -- $spec
  m="$1"; t="$2"
  n=$(echo "${m}_${t}" | tr -c 'a-zA-Z0-9' '_')
  curl -s --max-time 20 "http://localhost:19115/probe?target=${t}&module=${m}&debug=true" > "$D/${n}.log" 2>&1
  ok=$(grep -E '^probe_success ' "$D/${n}.log" | tail -1 | awk '{print $2}')
  dur=$(grep -E '^probe_duration_seconds ' "$D/${n}.log" | tail -1 | awk '{print $2}')
  err=$(grep -ioE '(deadline exceeded|connection refused|no such host|i/o timeout|x509[^"]{0,60}|remote error:[^"]{0,50}|tls:[^"]{0,50}|bad status[^"]{0,30}|unsupported protocol|getsockopt[^"]{0,40}|context canceled)' "$D/${n}.log" | sort -u | head -2 | paste -sd'; ' -)
  printf "  %-11s %-28s %-5s %-9s %s\n" "$m" "$(echo -n "$t" | cut -c1-28)" "$ok" "$(awk -v d="${dur:-0}" 'BEGIN{printf "%.0fms", d*1000}')" "${err:--}"
done

echo
echo "=== B. the pod's own route split (which ranges really do go via VLAN 31) ==="
kubectl -n "$NAMESPACE" exec deploy/blackbox-exporter-vpn -- ip route 2>/dev/null \
  | awk '{print "   "$0}' | head -20

echo
echo "=== C. reference egress IP of the plain WAN (the Mac, no VPN) ==="
printf "   WAN exit IP: "
curl -s --max-time 15 https://api.ipify.org || echo "(unreachable)"
echo
echo "=== D. egress IP as seen from INSIDE VLAN 31 (this is the test) ==="
echo "   if this returns 210.186.239.63 -> VLAN 31 is NOT exiting via Proton"
echo "   any other IP                    -> it is exiting via Proton (and egress works)"
for pod in "default/changedetection" "downloads/metube"; do
  ns=${pod%%/*}; name=${pod##*/}
  echo "-- $ns/$name"
  kubectl -n "$ns" exec "deploy/$name" -- python3 -c "
import urllib.request, socket
socket.setdefaulttimeout(12)
for u in ('https://api.ipify.org', 'http://1.1.1.1/', 'https://ifconfig.me/ip'):
    try:
        r = urllib.request.urlopen(u)
        print('     %-28s HTTP %s  %s' % (u, r.status, r.read()[:48].decode('utf8','replace').strip()))
    except Exception as e:
        print('     %-28s FAIL %s: %s' % (u, type(e).__name__, str(e)[:80]))
" 2>&1 | tail -4 | sed 's/^/   /'
done

kill $PF 2>/dev/null
