#!/usr/bin/env bash
# 001 — What is actually firing? Active alerts from Alertmanager (read-only).
# Path: no shell in prometheus image; alertmanager (busybox) has wget.
set -euo pipefail
NS=observability

kubectl -n "$NS" exec alertmanager-kube-prometheus-stack-0 -c alertmanager \
  -- wget -qO- 'http://localhost:9093/api/v2/alerts' \
| python3 -c '
import json,sys,collections
d=json.load(sys.stdin)
act=[a for a in d if a["status"]["state"]=="active"]
c=collections.Counter((a["labels"].get("alertname"),a["labels"].get("severity")) for a in act)
for (n,s),k in sorted(c.items()):
    print(f"{k:>3}  {n:<28} {s}")
print("total active:",len(act))
print()
for a in act:
    if "Probe" in a["labels"].get("alertname",""):
        l=a["labels"]
        print(l["alertname"], "|", l.get("job"), "|", l.get("instance"),
              "|", l.get("service"), "| starts", a["startsAt"])
'

# Red herring check: the Completed blackbox pod is an old drain leftover.
kubectl -n "$NS" get deploy blackbox-exporter blackbox-exporter-vpn -o wide
kubectl -n "$NS" get pods -l app.kubernetes.io/instance=blackbox-exporter-vpn -o wide
