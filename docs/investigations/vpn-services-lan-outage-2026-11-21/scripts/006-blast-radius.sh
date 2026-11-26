#!/usr/bin/env bash
# 006 — Blast radius: is this a real outage or a flaky probe?
# Throughput of every workload pinned to the VPN VLAN, before vs after.
set -euo pipefail
NS=observability

kubectl -n "$NS" port-forward pod/prometheus-kube-prometheus-stack-0 19090:9090 >/dev/null 2>&1 &
PF=$!; trap 'kill $PF' EXIT; sleep 5
NOW=$(date +%s); START=$((NOW-259200))

echo "=== per-pod rx over 3d @1h:  '#' >1kB/s (real transfer)  '.' >10  ' ' idle"
curl -sG --max-time 25 "http://localhost:19090/api/v1/query_range" \
  --data-urlencode 'query=sum by (pod) (rate(container_network_receive_bytes_total{pod=~"sabnzbd.*|slskd.*|metube.*|shelfmark.*"}[15m]))' \
  --data-urlencode "start=$START" --data-urlencode "end=$NOW" --data-urlencode "step=3600" \
| python3 -c '
import json,sys
for r in json.load(sys.stdin).get("data",{}).get("result",[]):
    v=r["values"]
    bar="".join("#" if float(x)>1000 else ("." if float(x)>10 else " ") for _,x in v)
    pod=r["metric"].get("pod","")
    print("  %-26s [%s]" % (pod, bar))
'

# Observed: slskd-0 streamed '#' for the first ~30 samples then flatlined at the
# outage boundary and has held ~320 B/s (keepalive) since -> real data loss.

echo "=== all pods that share the broken VLAN (same next hop 10.10.31.1)"
kubectl get pods -A -o json | python3 -c '
import json,sys
for i in json.load(sys.stdin)["items"]:
    a=i["metadata"].get("annotations") or {}
    for k,v in a.items():
        if "cncf.io/networks" in k and "\"vpn\"" in v:
            print("  ",i["metadata"]["namespace"], i["metadata"]["name"], v.replace("\n",""))
'

echo "=== unrelated alerts, for separation"
kubectl -n "$NS" exec alertmanager-kube-prometheus-stack-0 -c alertmanager \
  -- wget -qO- 'http://localhost:9093/api/v2/alerts' | python3 -c '
import json,sys,collections
d=json.load(sys.stdin)
act=[a for a in d if a["status"]["state"]=="active"]
for (n,s),k in sorted(collections.Counter((a["labels"].get("alertname"),a["labels"].get("severity")) for a in act).items()):
    print(f"  {k:>3}  {n:<24} {s}")
'
# 22x KubeHpaMaxedOut + 4x KubeJobFailed (ai-inference-smoke-test, renovate
# chaijunkin-discovery) are separate issues, not blackbox-related.
