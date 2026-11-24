#!/usr/bin/env bash
# 005 — Blackbox debug trace + firewall counters for VPN_SERVICES_LAN (vlan0.31.1).
# Distinguishes "timeout" from "instant no-route", and shows where packets drop.
set -euo pipefail
NS=observability

echo "=== ICMP 1.1.1.1 via VPN exporter, debug=1"
kubectl get --raw "/api/v1/namespaces/$NS/services/blackbox-exporter-vpn:9115/proxy/probe?target=1.1.1.1&module=icmp&debug=1" \
  | grep -E 'probe_(success|timeout_seconds|icmp_duration_seconds)'
# observed: phase="resolve" 3.8e-06, phase="rtt" 0, timeout 5 -> sent, zero replies.

echo "=== HTTP one.one.one.one via VPN exporter, debug=1"
kubectl get --raw "/api/v1/namespaces/$NS/services/blackbox-exporter-vpn:9115/proxy/probe?target=https%3A%2F%2Fone.one.one.one&module=http_2xx&debug=1" \
  | grep -E 'probe_(success|http_duration_seconds|dns_lookup_time_seconds|http_status_code)'
# observed: resolve=0.010s (DNS fine), connect=0 (syscall errored instantly), status_code 0.

kubectl -n "$NS" port-forward pod/prometheus-kube-prometheus-stack-0 19090:9090 >/dev/null 2>&1 &
PF=$!; trap 'kill $PF' EXIT; sleep 5
Q(){ echo "-- $1"; curl -sG --max-time 20 "http://localhost:19090/api/v1/query" \
       --data-urlencode "query=$1" | python3 -c '
import json,sys
rs=json.load(sys.stdin).get("data",{}).get("result",[])
if not rs: print("     (no data)")
for r in rs:
    m={k:v for k,v in r["metric"].items() if k in ("interface","name","service")}
    print("    ",m,"=",round(float(r["value"][1]),2))
'; }

echo "=== per-interface IPv4 pass vs block (1h) — vlan0.31.1 = VPN_SERVICES_LAN"
Q 'increase(opnsense_firewall_in_ipv4_pass_packets[1h])'
Q 'increase(opnsense_firewall_in_ipv4_block_packets[1h])'
Q 'increase(opnsense_firewall_out_ipv4_block_packets[1h])'

echo "=== OPNsense services (look for stopped) + reboot-pending flags"
Q 'opnsense_services_status'
Q 'opnsense_services_stopped_total'
Q 'opnsense_firmware_needs_reboot'
Q 'opnsense_firmware_upgrade_needs_reboot'
# observed: crowdsec = 0 (stopped); needs_reboot = 1. Both are leads, NOT proof.
