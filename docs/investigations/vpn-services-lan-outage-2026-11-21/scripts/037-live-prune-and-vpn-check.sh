#!/usr/bin/env bash
# Step 037 - Live state check after PR #2608 (READ-ONLY).
#
# Two questions in one pass:
#   1. Is the cluster still holding exactly the objects #2608 will prune? (nothing was deleted early,
#      and nothing new appeared that depends on volsync)
#   2. Did the VPN outage change since the last snapshot - the user was going to repoint Proton, and
#      #2604's VpnTunnelUpButNoReturn is the alert that should still be firing while it is broken.
set -uo pipefail

PROM="http://localhost:9091/api/v1"   # assumes: kubectl -n observability port-forward svc/prometheus-operated 9091:9090
PX() { curl -sf --max-time 15 "$PROM/query" --data-urlencode "query=$1" | python3 -c '
import json,sys
d=json.load(sys.stdin)
for r in d["data"]["result"]:
    m=r["metric"]; v=r["value"][1]
    keep={k:v2 for k,v2 in m.items() if k in ("alertname","device","peer_name","job","instance","name","state","severity")}
    print(f"    {v:>14}  {keep}")
' 2>/dev/null || echo "    (prometheus unreachable - is the port-forward up?)"; }

echo "===================================================================================================="
echo "1. PR #2608 state"
echo "===================================================================================================="
gh pr view 2608 --repo chaijunkin/home-ops --json state,mergedAt,mergeCommit,mergeStateStatus \
  --jq '"  state=\(.state) merged=\(.mergedAt // "-") commit=\(.mergeCommit.oid // "-" | .[0:9]) mergeState=\(.mergeStateStatus)"' 2>&1 | sed 's/^/  /'

echo
echo "===================================================================================================="
echo "2. Objects #2608 will prune (should still be Present until it merges)"
echo "===================================================================================================="
echo "  namespace volsync-system:"; kubectl get ns volsync-system --no-headers 2>&1 | sed 's/^/    /'
echo "  its contents:"; kubectl get all,secret,serviceaccount,alert,provider,ocirepository -n volsync-system --no-headers 2>&1 | sed 's/^/    /'
echo "  remediation webhook deployment:"; kubectl get deploy remediation-webhook -n observability --no-headers 2>&1 | sed 's/^/    /'
echo "  remediation cronjob:"; kubectl get cronjob remediation -n jobs --no-headers 2>&1 | sed 's/^/    /'
echo "  the live snapshot-controller that MUST survive:"; kubectl get deploy snapshot-controller -n kube-system --no-headers 2>&1 | sed 's/^/    /'
echo "  volsync CRDs (still expected - deletion is a separate decision):"; kubectl get crd --no-headers 2>&1 | grep volsync | sed 's/^/    /'
echo "  volsync CRs anywhere (must stay 0):"; kubectl get replicationsources,replicationdestinations -A --no-headers 2>&1 | sed 's/^/    /' | head -5
echo "  Flux app Kustomizations naming volsync/webhook/remediation (should vanish after merge):"
kubectl get kustomizations -A --no-headers 2>&1 | grep -Ei "volsync|webhook|remediation" | sed 's/^/    /' || echo "    none"

echo
echo "===================================================================================================="
echo "3. VPN egress: is Proton still not forwarding?"
echo "===================================================================================================="
echo "  VPN probe success (0 = VLAN31 egress dead):"; PX 'blackbox_probe_success{job="blackbox-exporter-vpn"}'
echo "  all probe targets by job:"; PX 'up{job=~"blackbox-exporter.*|speedtest-exporter|opnsense-exporter"}'
echo "  wireguard handshake age in seconds (wg2 = egress tunnel):"; PX 'time() - opnsense_wireguard_peer_last_handshake_seconds'
echo "  wireguard peer status:"; PX 'opnsense_wireguard_peer_status'
echo "  interface status for wg1/wg2:"; PX 'opnsense_interfaces_status{device_name=~"wg.*"}'
echo "  gateway status / loss:"; PX 'opnsense_gateways_status'
echo "  gateway monitoring enabled (0 = dpinger off, the WAN_PPPOE to-do):"; PX 'opnsense_gateways_monitor_info'

echo
echo "===================================================================================================="
echo "4. Alert state (firing + pending)"
echo "===================================================================================================="
echo "  firing by name:"; PX 'count by (alertname) (ALERTS{alertstate="firing"})'
echo "  VPN/backup/gateway/watchdog rules specifically:"
PX 'ALERTS{alertname=~"Vpn.*|BlackboxProbeFailed|Opnsense.*|SpeedtestExporterAbsent|Kopiur.*Failed|Watchdog"}'
echo "  rule health for the rules #2604/#2607 shipped + the deleted VolSyncVolumeOutOfSync:"
curl -sf --max-time 20 "$PROM/rules" 2>/dev/null | python3 -c '
import json,sys
want=("VpnTunnelUpButNoReturn","VpnProbeFailed","OpnsenseServiceStopped","CloudflareTunnelOffline",
      "DragonflyHighMemoryUsage","AutobrrNetworkUnmonitored","OpnsenseApiExporterAbsent",
      "VpnEgressProbesAbsent","VpnEgressTunnelAbsent","OpnsenseExporterEndpointErrors","VolSyncVolumeOutOfSync")
d=json.load(sys.stdin)
found=set()
for g in d["data"]["groups"]:
    for r in g["rules"]:
        if r["name"] in want:
            found.add(r["name"])
            print(f"    {r[\"name\"]:32s} health={r[\"health\"]:6s} state={r.get(\"queryless\",r.get(\"state\",\"-\"))} lastError={(r.get(\"lastError\") or \"-\")[:50]}")
for w in want:
    if w not in found:
        print(f"    {w:32s} NOT DEPLOYED (expected for VolSyncVolumeOutOfSync)")
' 2>/dev/null || echo "    (rules endpoint unreachable)"
