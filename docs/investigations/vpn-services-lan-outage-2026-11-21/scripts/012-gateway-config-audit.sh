#!/usr/bin/env bash
# Step 012 - the gateway configuration itself, read out of OPNsense.
#
# READ-ONLY: one GET of the config backup (the only endpoint that exposes the full
# gateways/policy-route/CARP picture), parsed locally. config.xml is NEVER stored in
# this repo - keep OUT under the approved temp dir.
#
# Question being answered: can something in the gateway config (a failover group, two
# default gateways, ECMP weighting, policy routes, DNS, PPPoE options) explain erratic
# throughput, as opposed to the ISP path?
set -uo pipefail
NAMESPACE=observability
POD=opnsense-read
OUT=${OUT:-./out}
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

kubectl -n "$NAMESPACE" exec "$POD" -- sh -c \
  'curl -sk --max-time 60 --user "$OPNSENSE_EXPORTER_OPS_API_KEY:$OPNSENSE_EXPORTER_OPS_API_SECRET" "https://$OPNSENSE_EXPORTER_OPS_API/api/core/backup/download/this"' > "$OUT/config.xml"
echo "  fetched $(wc -c < "$OUT/config.xml" | tr -d ' ') bytes -> $OUT/config.xml"
echo

python3 - "$OUT/config.xml" <<'PY'
import sys, xml.etree.ElementTree as ET
root = ET.parse(sys.argv[1]).getroot()
def txt(e,t,d=''): 
    c=e.find(t); return (c.text or '').strip() if c is not None and c.text else d
def flag(e,t): return e.find(t) is not None

print("=== GATEWAYS (System ▸ Gateways) ===")
gws = root.find('gateways')
default_count = 0
monitored = 0
for g in (gws.findall('gateway') if gws is not None else []):
    name = txt(g,'name')
    dis  = flag(g,'disabled')
    dflt = flag(g,'defaultgw')
    mon  = txt(g,'monitor','—')
    if dflt: default_count += 1
    if mon not in ('—','') and not dis: monitored += 1
    print(f"  {name:<26} iface={txt(g,'interface'):<8} gw={txt(g,'gateway'):<18} "
          f"default={'YES' if dflt else 'no ':<3} disabled={'YES' if dis else 'no':<3} monitor={mon}")
    for k in ('weight','priority','interval','timeout','failover_delay','tier'):
        if g.find(k) is not None: print(f"        {k} = {txt(g,k)}")
print(f"  -> default gateways: {default_count}   gateways actually monitored: {monitored}")

print("\n=== GATEWAY GROUPS (a group would mean the default can fail over) ===")
groups = [e for e in root.iter() if e.tag in ('group','gatewaygroup')]
if gws is not None:
    for e in gws:
        if e.tag not in ('gateway',): print('  <%s> ...' % e.tag)
found=False
for g in groups:
    found=True
    print('  group:', {c.tag:(c.text or '').strip() for c in g if c.tag not in ('item','gateway_item')})
    for it in g.findall('item'):
        d={c.tag:(c.text or '').strip() for c in it}
        print('     member:', d)
if not found: print("  none")

print("\n=== VIRTUAL IPs / CARP (a VIP can move the gateway) ===")
vip = root.find('virtualip')
if vip is None or not list(vip): print("  none")
for v in vip.findall('vip'):
    print('  ', {c.tag:(c.text or '').strip() for c in v})

print("\n=== POLICY ROUTES (Firewall ▸ NAT ▸ Outbound / policy routing) ===")
pr = root.find('policyroutes')
rows = pr.findall('policyroute') if pr is not None else []
print(f"  {len(rows)} policy routes")
for r in rows[:14]:
    print('   enabled=%-5s interface=%-8s source=%-22s dst=%-18s gw=%s' % (
        'no' if flag(r,'disabled') else 'yes', txt(r,'interface','any'), txt(r,'source','any'),
        txt(r,'destination','any'), txt(r,'gateway','-')))

print("\n=== STATIC ROUTES ===")
sr = root.find('staticroutes')
rows = sr.findall('route') if sr is not None else []
print(f"  {len(rows)} static routes")
for r in rows[:14]:
    print('   ', txt(r,'network'), '->', txt(r,'gateway'))

print("\n=== WAN / PPPoE ===")
ifc = root.find('interfaces')
for e in ifc:
    if e.tag in ('if','groups','group_members'): continue
    if txt(e,'iftype')=='pppoe' or txt(e,'enable')=='enabled' and e.tag in ('wan','wanppp','wanopt'):
        print(f"  {e.tag}: enable={txt(e,'enable','-')} iptype={txt(e,'iptype','-')} "
              f"gateway={txt(e,'gateway','-')} ipaddr={txt(e,'ipaddr','-') or '-'} mtu={txt(e,'mtu','default')} "
              f"pppoe_username={txt(e,'username','-')}")
for pp in root.iter('pppoe'):
    print('  pppoe block:', {c.tag:(c.text or '').strip() for c in pp if c.tag in ('username','password','service','mtu','mru','pppoe-localaddr','pppoe-remoteid','pppoe-provider','pppoe-disable')})

print("\n=== DNS the LAN clients get, and what the firewall uses ===")
sysn = root.find('system')
print('  system nameserver:', [ (n.text or '').strip() for n in sysn.findall('nameserver') ])
print('  DNS64/register DHCP DNS:', txt(sysn,'dnsallowoverride','default'), '/', txt(sysn,'dns34','unset'))
for e in root.iter('unbound'):
    keys={c.tag:(c.text or '').strip() for c in e if c.tag in ('enable','dnssec','dot','dns64','sslcert','port','activerequestlimit')}
    if keys: print('  unbound:', keys)
    for u in e.findall('dns_server'):
        print('     upstream:', {c.tag:(c.text or '').strip() for c in u})

print("\n=== SHAPING / OFFLOAD / TUNABLES that could throttle ===")
for tag in ('shaper','altq','dnshaper','tunables','system_performance'):
    n=len(list(root.iter(tag)))
    print(f"  <{tag}> blocks: {n}")
t=root.find('tunables')
if t is not None:
    for item in t.findall('item'):
        d={c.tag:(c.text or '').strip() for c in item}
        print('   tunable:', d.get('directory'), d.get('var'), '=', d.get('value'))
hw = sysn.find('hardware')
if hw is not None: print('  system/hardware:', {c.tag:(c.text or '').strip() for c in hw})
PY

echo
echo "cleanup:  kubectl -n $NAMESPACE delete pod $POD"
