#!/bin/sh
# 007 — OPNsense read-only diagnostic for the VPN_SERVICES_LAN egress outage.
#
# Run ON THE FIREWALL as root:   sh opnsense-vpn-diag.sh
# Then bring the printed file back and drop it beside this script's results/.
#
# READ-ONLY BY CONSTRUCTION. It only runs show/list/dump/inspect commands.
# It never calls filter_configure, apply, restart, reload, flush, delete,
# ifconfig ... up/down, or edits /conf/config.xml. Every decision it informs
# is left to a human.
#
# Decides between the two remaining hypotheses:
#   (A) stale CrowdSec remediation in a pf table  -> sections 3 and 4
#   (B) VLAN 31 policy route / alias / outbound NAT -> sections 5 and 6
# Section 2 is the decisive one: it names the rule that kills the packet.

set -u
OUT="/var/tmp/opnsense-vpn-diag-$(date +%Y%m%d-%H%M%S).txt"
VLAN_IF="vlan0.31.1"          # VPN_SERVICES_LAN
VPN_GW_IF="wg2"               # WAN_ProtonVPNSingapore
POD_IP="10.10.31.20"          # blackbox-exporter-vpn
POD_NET="10.10.31.0/24"
TARGET="1.1.1.1"

log() { printf '\n===== %s =====\n' "$*"; }

{
echo "# OPNsense VPN_SERVICES_LAN diagnostic  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "# kernel: $(uname -sr)"
[ -r /etc/version ] && echo "# opnsense: $(cat /etc/version)"

# 1. Interface and L2 sanity -------------------------------------------------
log "1. interfaces: ${VLAN_IF} and ${VPN_GW_IF}"
ifconfig "${VLAN_IF}" 2>&1
ifconfig "${VPN_GW_IF}" 2>&1
echo "-- wireguard peer detail (kernel if_wg; 'wg' CLI may not exist)"
ifconfig "${VPN_GW_IF}" 2>&1 | grep -iE 'wgdevice|wgpeer|wgaip|wqlang' || echo "   (no wg lines)"
command -v wg >/dev/null 2>&1 && wg 2>&1 || echo "   (wg CLI absent, expected on stock OPNsense)"

# 2. DECISIVE: which rule acts on the packet --------------------------------
# CLI equivalent of Diagnostics -> Rule Test. If this syntax is rejected by
# your pf build, use the GUI Rule Test instead:
#   Protocol ICMP, Source 10.10.31.20, Destination 1.1.1.1
log "2. rule evaluation for ${POD_IP} -> ${TARGET} (icmp) and -> one.one.one.one (tcp/443)"
pfctl -m "in on ${VLAN_IF} proto icmp from ${POD_IP} to ${TARGET}" 2>&1
pfctl -m "in on ${VLAN_IF} proto tcp from ${POD_IP} to any port 443" 2>&1
pfctl -m "in on ${VLAN_IF} proto icmp from any to 10.10.31.1" 2>&1
echo "-- note: 'block' here with an anchor naming crowdsec => hypothesis A."
echo "--         'block' naming your own policy, or no gateway => hypothesis B."

# 3. All rules on the VLAN, with anchor provenance --------------------------
log "3. pf rules mentioning ${POD_NET} / ${VLAN_IF}, with anchors"
pfctl -sr -vv 2>&1 | grep -iE -B3 -A3 '31\.0/24|vpn_services' || echo "   (no matches)"
log "3b. anchors present (crowdsec installs its own)"
pfctl -sr -An 2>&1 | sort -u | head -40

# 4. Tables: does a ban table hold our pod/subnet? --------------------------
log "4. pf tables"
pfctl -sT 2>&1
for t in $(pfctl -sT 2>/dev/null); do
  echo "-- table ${t}: $(pfctl -t "${t}" -T show 2>/dev/null | grep -c '^ *')"
  pfctl -t "${t}" -T show 2>/dev/null | grep -E '10\.10\.31|'"${TARGET}" && \
    echo "   ^^^ HIT in table ${t}"
done
log "4b. crowdsec service + decisions"
service crowdsec status 2>&1 || echo "   (crowdsec service not found/ stopped)"
command -v cscli >/dev/null 2>&1 || echo "   (cscli not on PATH)"
cscli decisions list -f json 2>&1 | head -100
cscli alerts list --limit 25 2>&1 | head -40
echo "-- bouncer package"
pkg query '%n %v %F' 'crowdsec*' 2>&1 || pkg info 2>&1 | grep -i crowdsec || true

# 5. Routing: is the policy route to the VPN gateway actually installed? ----
log "5. routing table"
netstat -rn -f inet 2>&1 | head -60
log "5b. route to ${TARGET} (which gateway/device does the kernel pick)"
route -n get "${TARGET}" 2>&1
route -n get "${TARGET}" -interface "${VPN_GW_IF}" 2>&1
command -v configctl >/dev/null 2>&1 && \
  { echo "-- gateways as OPNsense sees them"; configctl routing gateways show 2>&1 | head -60; } || \
  echo "   (configctl gateways unavailable on this version)"

# 6. Outbound NAT -----------------------------------------------------------
# Missing NAT for ${POD_NET} on wg2 = packets leave with a source outside the
# tunnel's range and Proton silently drops them: healthy tunnel, zero return.
log "6. NAT / translation state"
pfctl -s nat 2>&1 | head -40
echo "-- (newer pf replaced -s nat with the translation anchor; try both)"
pfctl -s Sources 2>&1 | head -40
pfctl -sr -vv 2>&1 | grep -iE -B2 -A2 'nat on '"${VPN_GW_IF}" || echo "   (no nat on ${VPN_GW_IF} found)"

# 7. Config as written: alias, policy gateway, NAT mode ---------------------
# A renamed/deleted alias silently detaches from policies and outbound NAT.
log "7. config.xml excerpts"
echo "-- aliases referencing ${POD_NET}"
grep -n -A6 -iE '<name>.*(vpn|31).*</name>' /conf/config.xml 2>/dev/null | grep -iE 'name|network|type' | head -40
echo "-- firewall rules on ${VLAN_IF}: gateway element present?"
grep -n -B2 -A22 'vpn_services' /conf/config.xml 2>/dev/null | grep -iE "interface|<gateway>|<source>|<destination>|<action>|disabled|<protocol>" | head -60
echo "-- outbound NAT mode (automatic | hybrid | disable)"
grep -n -A4 '<outbound>' /conf/config.xml 2>/dev/null | head -20
echo "-- wireguard instance for the exit + its peers"
grep -n -A30 -iE 'proton|singapore' /conf/config.xml 2>/dev/null | head -60

# 8. Live proof of life: do probes arrive, do replies leave? ----------------
# Run this while the agent triggers probes, ~20s is enough.
log "8. packet capture (20s) -- run while probes are being triggered"
echo "-- on ${VLAN_IF}: expect echo-request in, and echo-reply OUT if healthy"
timeout 20 tcpdump -ni "${VLAN_IF}" -c 60 'icmp and (net '"${POD_NET}"' or host 10.10.31.1)' 2>&1 | tail -30
echo "-- on ${VPN_GW_IF}: expect traffic here only if forwarding reached the tunnel"
timeout 20 tcpdump -ni "${VPN_GW_IF}" -c 60 'icmp or tcp port 443' 2>&1 | tail -30

# 9. Recent filter/log evidence --------------------------------------------
log "9. recent filter log lines for ${POD_NET}"
grep -hE '10\.10\.31\.' /var/log/filter.log 2>/dev/null | tail -40 || echo "   (filter.log empty; check Status -> Firewall -> Live View)"
log "9b. crowdsec log tail"
tail -40 /var/log/crowdsec.log 2>/dev/null || echo "   (no /var/log/crowdsec.log)"
grep -hi crowdsec /var/log/system.log 2>/dev/null | tail -20

log "done"
echo "# collected into ${OUT}"
} 2>&1 | tee "${OUT}"

echo "\nSaved: ${OUT}"
echo "Interpretation guide: section 2 names the acting rule; sections 3-4 attribute"
echo "it to CrowdSec, sections 5-7 attribute it to policy route / alias / NAT."
