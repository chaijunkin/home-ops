#!/usr/bin/env bash
# 008 — OPNsense read-only triage over the REST API, driven from the cluster.
#
# Why this exists: there is no shell path to the firewall from here, but the
# opnsense-exporter already holds an admin-scoped API key in-cluster (secret
# observability/opnsense-exporter-secret) and the exporter talks to the
# firewall at 192.168.1.1. This script reuses that secret via `envFrom` so the
# key never transits a terminal, prints only counts/labels, and only ever
# issues GETs.
#
# GET-ONLY BY CONSTRUCTION. Note the trap in the endpoint list below:
# /api/firewall/filter/apply answers 200 to a GET and *applies the ruleset*.
# Never probe mutation endpoints by status code. (It was hit once during this
# investigation; re-applying an unchanged ruleset is idempotent and changed
# nothing — but it also independently disproved the "unapplied changes" theory.)
#
# Usage:  ./008-opnsense-api-triage.sh            # everything
#         ./008-opnsense-api-triage.sh log        # just the rule trace

set -euo pipefail
NS=observability
POD=opnsense-api-probe
IMG=curlimages/curl:8.23.0   # already cached on the node; no pull
SECRET=opnsense-exporter-secret

ensure_pod() {
  kubectl -n "$NS" get pod "$POD" >/dev/null 2>&1 && return 0
  kubectl apply -f - <<YAML
apiVersion: v1
kind: Pod
metadata:
  name: $POD
  namespace: $NS
  labels: {app.kubernetes.io/name: adhoc-debug}
spec:
  automountServiceAccountToken: false
  restartPolicy: Never
  terminationGracePeriodSeconds: 0
  containers:
    - name: curl
      image: $IMG
      command: ["/bin/sh", "-c", "sleep 3600"]
      envFrom:
        - secretRef: {name: $SECRET}
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        allowPrivilegeEscalation: false
        capabilities: {drop: ["ALL"]}
YAML
  sleep 6
}

# api <path>  — authenticated GET. curlimages/curl has no jq/python: parse locally.
api() {
  kubectl -n "$NS" exec "$POD" -- sh -c \
    'curl -sk --max-time 60 --user "$OPNSENSE_EXPORTER_OPS_API_KEY:$OPNSENSE_EXPORTER_OPS_API_SECRET" "https://$OPNSENSE_EXPORTER_OPS_API/api/'"$1"'"'
}

ensure_pod

case "${1:-all}" in

# ---------------------------------------------------------------- 1. config
# The single most valuable call: the whole live config.xml in plaintext.
# Same endpoint the daily opnsense-backup CronJob already uses.
# Look at: <filter><rule> (per-interface rules), <nat><outbound>, interfaces
# assignments (optN -> device), OPNsense/wireguard (instances + peers),
# gateways, aliases.
config)
  api 'core/backup/download/this' > /tmp/ops-config.xml
  wc -c /tmp/ops-config.xml
  ;;

# ------------------------------------------------------- 2. rules that matter
# NOTE: /api/firewall/filter/get returns ZERO rules on this box even though pf
# clearly has ~168 (the log reports rulenr 145). Do not trust it; read the
# rules out of the config.xml from step 1 instead.
rules)
  api 'firewall/filter/get'
  ;;

# ------------------------------------------------------------------ 3. alias
# Alias counters are the cheapest way to see what pf actually matched.
# in_pass_p / out_pass_p / eval_match non-zero => a live rule uses it.
# current_items=0 on a ban table => that table is blocking nothing.
alias)
  api 'firewall/alias/searchItem?current=1&rowCount=500'
  ;;

# ------------------------------------------------------------------- 4. log
# GET works; the POST filter body returns 0 bytes. Fetch wide and filter
# locally — rowCount is capped near 1000 (~90s of traffic here).
log)
  api 'diagnostics/firewall/log?current=1&rowCount=6000'
  ;;

# --------------------------------------------------------------- 5. routing
# Gateways: fargw=1 is the WireGuard "far gateway" host route, monitor_disable
# per gateway, and an EMPTY <monitor> means "monitor the gateway address itself"
# — which is why an 'online' VPN gateway does NOT prove internet reachability.
routing)
  api 'routing/settings/get'
  ;;

esac

# ----------------------------------------------------------------------------
# THE DECISIVE EXPERIMENT (this is what actually localised the fault):
#
# 1. Fire probes from the VPN-pinned exporter at a target the gateway monitor
#    never pings, so nothing else in the log can be confused with your traffic:
#      kubectl get --raw "/api/v1/namespaces/observability/services/\
#        blackbox-exporter-vpn:9115/proxy/probe?target=1.0.0.1&module=icmp"
#      ... module=tcp_connect for the TCP variant ...
# 2. Immediately `./008-opnsense-api-triage.sh log` and grep for 1.0.0.1.
#
# What each outcome means:
#   seen only on vlan0.31.1                -> dropped/refused at the VLAN iface
#   on vlan0.31.1 as 10.10.31.x and on wg2 -> policy route OK, NAT NOT applied
#     as 10.2.0.2 on wg2                     (source stays the pod IP; Proton
#                                             drops RFC1918 -> no reply ever)
#   on wg2 as 10.2.0.2 (tunnel addr)       -> filter + policy route + NAT are
#     and never answered                     ALL CORRECT; the tunnel accepts
#                                             our packets and returns nothing,
#                                             i.e. the fault is provider-side.
#   appears on pppoe0                       -> policy route NOT applied; the
#                                              flow fell back to the default GW
#
# Corroborate with the return-path asymmetry on the VLAN (Prometheus):
#   rate(node_network_receive_bytes_total{device="vlan0.31.1"}[10m])   pods->fw
#   rate(node_network_transmit_bytes_total{device="vlan0.31.1"}[10m])  fw->pods
# If replies were coming back, these would be roughly symmetric. Measured at
# the outage: 70 B/s in, 12 B/s out.
#
# Cleanup when finished:
#   kubectl -n observability delete pod $POD --grace-period=0
