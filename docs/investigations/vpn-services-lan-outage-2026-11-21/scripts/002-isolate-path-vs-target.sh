#!/usr/bin/env bash
# 002 — Isolate: is the TARGET broken, or the VPN PATH? Live probe both exporters.
# Read-only GET via the API-server service proxy (no port-forward, no shell needed).
set -euo pipefail
NS=observability

probe() { # svc module target
  echo "=== svc=$1 module=$2 target=$3"
  kubectl get --raw "/api/v1/namespaces/$NS/services/$1:9115/proxy/probe?target=$3&module=$2" \
    | grep -E '^(probe_success|probe_duration_seconds|probe_http_status_code|probe_ip_protocol)'
}

# Internet from the normal pod network  -> expected PASS
probe blackbox-exporter        icmp      1.1.1.1
probe blackbox-exporter        http_2xx  https%3A%2F%2Fone.one.one.one
# Internet from the VPN-pinned interface -> observed FAIL
probe blackbox-exporter-vpn    icmp      1.1.1.1
probe blackbox-exporter-vpn    http_2xx  https%3A%2F%2Fone.one.one.one
# The VPN gateway itself (on-link, no tunnel involved) -> observed FAIL
probe blackbox-exporter-vpn    icmp      10.10.31.1
# Another pod on the same VLAN (control) -> passes, but see caveat below
probe blackbox-exporter-vpn    icmp      10.10.31.15

# --- CAVEAT (learned the hard way) -----------------------------------------
# The cluster is SINGLE NODE (k8s-0 only). macvlan mode=bridge switches
# pod->pod in-kernel, so 10.10.31.20 -> 10.10.31.15 succeeding does NOT prove
# the physical uplink or the gateway are reachable. Do not treat it as a control.
kubectl get nodes -o wide

# How the VPN path is built: Multus secondary iface, macvlan on eth1, forced routes.
kubectl -n "$NS" get deploy blackbox-exporter-vpn -o yaml | grep -A6 'cncf.io/networks'
kubectl -n network get network-attachment-definition vpn -o yaml | head -40

# NOTE: probing PRIVATE ips on the *non-vpn* exporter is an invalid test — it is
# refused by blackbox's private-range restriction (the control target fails too).
