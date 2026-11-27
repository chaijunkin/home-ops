#!/usr/bin/env bash
# Step 014 - close the coverage gaps: OPNsense LIVE log and LIVE traffic, not just config.
#
# READ-ONLY: GET only, and the guard rejects any path whose *segment* is a verb, because
# /api/firewall/filter/apply answers 200 to a GET on this firewall and really applies the
# ruleset.
#
# Coverage so far was: full config.xml (yes), dpinger gateway status (yes), interface
# counters via node-exporter (yes). Missing was: the firewall's own live log, pf state
# detail, and any per-connection/flow view. This probes exactly those and reports which
# endpoints the API key can actually read (it answers 302 without auth, 404 when the
# endpoint does not exist, [] when it exists but yields nothing).
set -uo pipefail
NAMESPACE=observability
POD=opnsense-read
OUT=${OUT:-./out14}
mkdir -p "$OUT"

kubectl -n "$NAMESPACE" get pod "$POD" >/dev/null 2>&1 || cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata: {name: $POD, namespace: $NAMESPACE, labels: {app: opnsense-read}}
spec:
  restartPolicy: Never
  containers:
  - name: curl
    image: curlimages/curl:8.23.0
    args: ["sleep","900"]
    envFrom: [{secretRef: {name: opnsense-exporter-secret}}]
    resources:
      requests: {cpu: "20m", memory: "64Mi"}
      limits: {cpu: "200m", memory: "256Mi"}
EOF
kubectl -n "$NAMESPACE" wait --for=condition=Ready "pod/$POD" --timeout=120s

api(){
  local path=$1 qs=${2:-} seg name
  local IFS=/; local segs=($path); unset IFS
  for seg in "${segs[@]}"; do
    case "$seg" in
      apply|set|add|del|delete|remove|restart|start|stop|reboot|save|update|post|rollback|put|enable|disable|reconfigure|flush|cancel|send|mount)
        echo "   REFUSED (verb segment '$seg') /api/$path"; return;;
    esac
  done
  name=$(echo "$path" | tr '/' '_'); [ -n "$qs" ] && name="${name}_$(echo "$qs" | tr -c 'a-zA-Z0-9' '_')"
  kubectl -n "$NAMESPACE" exec "$POD" -- sh -c \
    'curl -sk --max-time 30 -w "\n%{http_code}" -H "Accept: application/json" --user "$OPNSENSE_EXPORTER_OPS_API_KEY:$OPNSENSE_EXPORTER_OPS_API_SECRET" "https://$OPNSENSE_EXPORTER_OPS_API/api/'"$path$qs"'"' > "$OUT/$name.raw" 2>&1
  local code=$(tail -1 "$OUT/$name.raw"); local size=$(wc -c < "$OUT/$name.raw" | tr -d ' ')
  printf '   %-3s %8s B  /api/%s%s\n' "$code" "$size" "$path" "$qs"
  [ "$code" = "200" ] && sed '$d' "$OUT/$name.raw" > "$OUT/$name.json" 2>/dev/null
}

echo "now: $(date -u '+%Y-%m-%d %H:%M:%S UTC')  /  $(date '+%H:%M:%S %Z')"
echo
echo "=== 1. LIVE firewall log (the one log endpoint the API exposed before) ==="
api diagnostics/firewall/log "?rowCount=400"
if [ -s "$OUT/diagnostics_firewall_log__rowCount_400_.json" ]; then
  python3 - "$OUT/diagnostics_firewall_log__rowCount_400_.json" <<'PY'
import json, sys, collections, time
raw=json.load(open(sys.argv[1]))
rows = raw.get('rows', raw) if isinstance(raw, dict) else raw
print(f"   rows returned: {len(rows)}")
if rows and isinstance(rows[0], dict):
    print("   fields:", sorted(rows[0].keys())[:14])
    byif=collections.Counter(); bydst=collections.Counter(); bysrc=collections.Counter(); reasons=collections.Counter()
    times=[]
    for r in rows:
        byif[r.get('interface','?')] += 1
        bydst[str(r.get('destination','?')).split(':')[0]] += 1
        bysrc[str(r.get('source','?')).split(':')[0]] += 1
        reasons[r.get('reason','?')] += 1
        t=r.get('time') or r.get('timetime')
        if t: times.append(str(t))
    print("   by interface:", dict(byif.most_common(8)))
    print("   by reason  :", dict(reasons.most_common(6)))
    print("   top sources:", dict(bysrc.most_common(8)))
    print("   top dests  :", dict(bydst.most_common(8)))
    if times: print("   log span (raw time fields):", min(times), "->", max(times))
else:
    print("   (empty body)")
PY
fi

echo
echo "=== 2. pf state table / firewall statistics (per-connection truth) ==="
api diagnostics/firewall/getStatesSummary
api diagnostics/firewall/getStateCount
api diagnostics/firewall/dump
api firewall/statistics/show
api diagnostics/firewall/getActiveFilterRules

echo
echo "=== 3. LIVE per-interface traffic straight from the firewall (not node-exporter) ==="
api diagnostics/interface/getInterfaceTraffic/pppoe0
api diagnostics/interface/getInterfaceRates
api diagnostics/interface/getInterfaceRates/pppoe0
api diagnostics/interface/getInterfacesTraffic
api diagnostics/interface/getIpInterface

echo
echo "=== 4. ARP + DNS in use by the firewall (is the path even resolving?) ==="
api diagnostics/interface/getARPTable
api diagnostics/interface/getArpTable
api diagnostics/interface/getInterfaceServers/pppoe0

echo
echo "=== 5. gateways right now (dpinger, current window) + what is registered in the API ==="
api routes/gateway/status
api core/api/service/list
api core/service/status

echo
echo "=== 6. system info / widget feeds (link speed, uptime, temperature via GUI path) ==="
api diagnostics/system/getSystemInfo
api diagnostics/system/getWidgetComponents
api core/system/getInfo

echo
echo "saved under $OUT"
echo "cleanup:  kubectl -n $NAMESPACE delete pod $POD"
