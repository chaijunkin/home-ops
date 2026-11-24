#!/usr/bin/env bash
# 004 — Is the VPN tunnel itself down? (It was NOT.) WireGuard + gateway monitor.
# The OPNsense exporter (job opnsense-exporter) exposes tunnel + gateway state.
set -euo pipefail
NS=observability

kubectl -n "$NS" port-forward pod/prometheus-kube-prometheus-stack-0 19090:9090 >/dev/null 2>&1 &
PF=$!; trap 'kill $PF' EXIT; sleep 5
Q(){ echo "-- $1"; curl -sG --max-time 20 "http://localhost:19090/api/v1/query" \
       --data-urlencode "query=$1" | python3 -c '
import json,sys,time
rs=json.load(sys.stdin).get("data",{}).get("result",[])
if not rs: print("     (no data)")
for r in rs:
    m=r["metric"]; v=r["value"][1]
    keep={k:x for k,x in m.items() if k in ("device","device_name","peer_name","name","address")}
    extra=""
    try:
        f=float(v)
        if f>1e8: extra=" -> "+time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime(f))+"Z"
    except: pass
    print("    ",keep,"=",v,extra)
'; }

echo "=== WG interface + peer status"
Q 'opnsense_wireguard_interfaces_status'
Q 'opnsense_wireguard_peer_status'
echo "=== peer last handshake, as AGE in seconds (small == healthy)"
Q 'time() - opnsense_wireguard_peer_last_handshake_seconds'
echo "=== OPNsense gateway monitoring: is the Proton gateway considered up?"
Q 'opnsense_gateways_status'
Q 'opnsense_gateways_loss_percentage'
Q 'opnsense_gateways_rtt_milliseconds'
Q 'opnsense_gateways_info'
echo "=== CARP / HA (would explain a dead VIP like 10.10.31.1)"
Q 'opnsense_carp_allowed'
Q 'opnsense_carp_demotion'
Q 'opnsense_carp_maintenance_mode'

echo "=== interface name map (find which VLAN is 10.10.31.0/24)"
Q 'opnsense_interfaces_mtu_bytes'

echo "=== VLAN31 tx collapsed at the same instant the probes died (B/s)"
NOW=$(date +%s); START=$((NOW-259200))
for dev in vlan0.31.1 wg2; do
  echo "-- $dev tx"
  curl -sG --max-time 25 "http://localhost:19090/api/v1/query_range" \
    --data-urlencode "query=rate(node_network_transmit_bytes_total{instance=~\"gateway.*\",device=\"$dev\"}[10m])" \
    --data-urlencode "start=$START" --data-urlencode "end=$NOW" --data-urlencode "step=900" \
  | python3 -c '
import json,sys,time
for r in json.load(sys.stdin).get("data",{}).get("result",[]):
    print("        "+" ".join("%s=%8.0f"%(time.strftime("%m-%d %H:%M",time.gmtime(ts)),float(v)) for ts,v in r["values"][::4]))
'
done
# NOTE metric is node_network_receive_bytes_total (NOT ..._received_...).
