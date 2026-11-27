#!/usr/bin/env bash
# Step 010 - ask OPNsense itself: is the *firewall* responsible for the slowdown?
#
# READ-ONLY. GET requests only. The guard rejects a path whose *segment* is a verb, so
# /api/firewall/filter/apply and /api/core/service/restart/... are refused while
# /api/routes/gateway/settings/get stays allowed. This matters here: on this firewall
# /api/firewall/filter/apply answers 200 to a GET and really does apply the ruleset.
#
# Why: dpinger reports WAN_PPPOE monitoring as disabled, so the firewall has never
# health-checked the real internet gateway. Meanwhile WAN latency went 7 ms -> 120-240 ms
# with the link <10% busy and the firewall itself showing headroom (states 1.2%,
# mbuf 2.9%, load1 avg 0.45). Ask it directly: gateway state, PPPoE session uptime,
# traffic shapers, and its own logs.
set -uo pipefail
NAMESPACE=observability
POD=opnsense-read
OUT=${OUT:-./out}
mkdir -p "$OUT"

kubectl -n "$NAMESPACE" get pod "$POD" >/dev/null 2>&1 || cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: $POD
  namespace: $NAMESPACE
  labels: {app: opnsense-read}
spec:
  restartPolicy: Never
  containers:
  - name: curl
    image: curlimages/curl:8.23.0
    args: ["sleep","1800"]
    envFrom:
    - secretRef: {name: opnsense-exporter-secret}
    resources:
      requests: {cpu: "20m", memory: "64Mi"}
      limits: {cpu: "200m", memory: "256Mi"}
EOF
kubectl -n "$NAMESPACE" wait --for=condition=Ready "pod/$POD" --timeout=120s

# api <path-without-/api-prefix> [query]   -- authenticated GET, status code recorded
api(){
  local path=$1 qs=${2:-} seg name segs
  local IFS=/; segs=($path); unset IFS
  for seg in "${segs[@]}"; do
    case "$seg" in
      apply|set|add|del|delete|remove|restart|start|stop|reboot|save|update|post|rollback|put|enable|disable|mount|send|cancel|reconfigure|flush)
        echo "   REFUSED (verb segment '$seg') /$path"; return;;
    esac
  done
  name=$(echo "$path" | tr '/' '_'); [ -n "$qs" ] && name="${name}_$(echo "$qs" | tr -c 'a-zA-Z0-9' '_')"
  kubectl -n "$NAMESPACE" exec "$POD" -- sh -c \
    'curl -sk --max-time 30 -w "\n%{http_code}" -H "Accept: application/json" --user "$OPNSENSE_EXPORTER_OPS_API_KEY:$OPNSENSE_EXPORTER_OPS_API_SECRET" "https://$OPNSENSE_EXPORTER_OPS_API/api/'"$path$qs"'"' > "$OUT/$name.raw" 2>&1
  local code=$(tail -1 "$OUT/$name.raw"); local size=$(wc -c < "$OUT/$name.raw" | tr -d ' ')
  printf '   %-3s %8s B  /api/%s%s\n' "$code" "$size" "$path" "$qs"
  [ "$code" = "200" ] && sed '$d' "$OUT/$name.raw" > "$OUT/$name.json" 2>/dev/null
}

echo "=== gateways & dpinger: does the firewall think a gateway is down? ==="
api routes/gateway/status
api routes/gateway/settings/get
api routes/routes/get
api routes/controlpppgw/get

echo
echo "=== PPPoE session: uptime proves a reconnect, addresses prove the path ==="
api diagnostics/ppp/getppp
api diagnostics/ppp/getpppinterfaces
api diagnostics/ppp/getinterfaces
api interfaces/ppp/settings/get
api interfaces/status/get
api diagnostics/interface/getInterfaceNames
api diagnostics/interface/getInterfaceStatus
api diagnostics/interface/getInterfacesStatus

echo
echo "=== shaping / offload: a shaper or lost HW offload throttles throughput ==="
api diagnostics/interface/getInterfaceQdisc/pppoe0
api diagnostics/interface/getInterfaceQuota/pppoe0
api shaper/pipe/list
api pyshaper/pipe/list
api plugin/pyshaper/pipe/list

echo
echo "=== config change history: did anything change on the firewall today? ==="
api core/backup/list
api diagnostics/system/getConfigHistory
api diagnostics/system/getLatestConfigChange

echo
echo "=== the firewall's own logs: date the degradation ==="
api diagnostics/log/settings/get
api diagnostics/log/ppp/ppp                    "?rowCount=250"
api diagnostics/log/routenotification/routenotification "?rowCount=250"
api diagnostics/log/system/system              "?rowCount=250"

echo
echo "=== services (crowdsec still stopped?) ==="
api core/service/list
api core/service/status

echo
echo "=== full config for offline grep (shaper, gw monitoring, offload, dns) ==="
api core/backup/download/this
echo
echo "saved under $OUT"
echo "cleanup when done:  kubectl -n $NAMESPACE delete pod $POD"
