#!/usr/bin/env bash
# 003 — Exact outage start + was it flapping? Reboot or config change?
# Prometheus has no wget; port-forward and query locally. Response key is
# "metric", NOT "labels". query_range needs absolute epochs, not -60h.
set -euo pipefail
NS=observability

kubectl -n "$NS" port-forward pod/prometheus-kube-prometheus-stack-0 19090:9090 >/dev/null 2>&1 &
PF=$!; trap 'kill $PF' EXIT; sleep 5
NOW=$(date +%s); START=$((NOW-259200))   # 3 days

echo "### transition points for VPN probes (5m step)"
curl -sG --max-time 25 "http://localhost:19090/api/v1/query_range" \
  --data-urlencode 'query=probe_success{job=~"probe/observability/vpn.*"}' \
  --data-urlencode "start=$START" --data-urlencode "end=$NOW" --data-urlencode "step=300" \
| python3 -c '
import json,sys,time
for r in json.load(sys.stdin)["data"]["result"]:
    m=r["metric"]; prev=None; trans=[]
    for ts,v in r["values"]:
        cur=(v=="1")
        if prev is not None and cur!=prev: trans.append((ts,"UP->DOWN" if not cur else "DOWN->UP"))
        prev=cur
    print(" ",m.get("job"),m.get("instance"))
    for ts,k in trans: print("   ",k,"@",time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime(ts)),"UTC")
'

echo "### node + firewall boot times (did everything reboot at once?)"
curl -sG --max-time 20 "http://localhost:19090/api/v1/query" \
  --data-urlencode 'query=node_boot_time_seconds' \
| python3 -c '
import json,sys,time
for r in json.load(sys.stdin)["data"]["result"]:
    m=r["metric"]; v=float(r["value"][1])
    who=m.get("kubernetes_node") or m.get("instance")
    print("  %-28s %s UTC" % (who, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(v))))
'

echo "### firewall itself reachable the whole time?"
curl -sG --max-time 25 "http://localhost:19090/api/v1/query_range" \
  --data-urlencode 'query=up{instance="gateway.cloudjur.com:9100"}' \
  --data-urlencode "start=$START" --data-urlencode "end=$NOW" --data-urlencode "step=1800" \
| python3 -c '
import json,sys,time
for r in json.load(sys.stdin)["data"]["result"]:
    v=r["values"]
    print("   ","".join("." if x=="1" else "X" for _,x in v))
    downs=[ts for ts,x in v if x!="1"]
    if downs: print("    down samples:",[time.strftime("%m-%d %H:%M",time.gmtime(t)) for t in downs])
'

# Container death at the node reboot, and absence of any GitOps change:
kubectl -n "$NS" get pod -l app.kubernetes.io/instance=blackbox-exporter-vpn \
  -o jsonpath='{.items[0].status.containerStatuses[0].restartCount}{"\n"}{.items[0].status.containerStatuses[0].lastState}{"\n"}'
git log --since=2026-11-19 --until=2026-11-23 --date=iso --pretty='%h %ad %s'
