#!/usr/bin/env bash
# Step 021 - watch the firewall's live log while VLAN 31 sends known traffic.
#
# READ-ONLY. Generates identifiable flows from a VLAN-31 pod, then reads
# /api/diagnostics/firewall/log (GET only, verb-segment guard as in step 014) and prints every
# row touching 10.10.31.x with its interface and rule number. This answers, from the firewall's
# own point of view, three things no metric could:
#   1. does the traffic leave, and on which interface (wg2 = via Proton, pppoe0 = direct)?
#   2. which rule allows it?
#   3. is any RETURN traffic logged at all?
set -uo pipefail
NAMESPACE=observability
POD=opnsense-read
OUT=${OUT:-./out21}
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
    args: ["sleep","600"]
    envFrom: [{secretRef: {name: opnsense-exporter-secret}}]
    resources:
      requests: {cpu: "20m", memory: "64Mi"}
      limits: {cpu: "200m", memory: "256Mi"}
EOF
kubectl -n "$NAMESPACE" wait --for=condition=Ready "pod/$POD" --timeout=120s

getlog(){
  kubectl -n "$NAMESPACE" exec "$POD" -- sh -c \
    'curl -sk --max-time 30 --user "$OPNSENSE_EXPORTER_OPS_API_KEY:$OPNSENSE_EXPORTER_OPS_API_SECRET" "https://$OPNSENSE_EXPORTER_OPS_API/api/diagnostics/firewall/log?rowCount=600"' > "$OUT/$1.json" 2>&1
  echo "   saved $OUT/$1.json ($(wc -c < "$OUT/$1.json" | tr -d ' ') B)"
}

echo "=== baseline log ==="; getlog before

echo
echo "=== generating known traffic from VLAN 31 (downloads/metube, source 10.10.31.x) ==="
kubectl -n downloads exec -i deploy/metube -- python3 - <<'PY' 2>&1 | tail -12 | sed 's/^/   /'
import socket, ssl, time
def tag(label, fn):
    try: print(f"{label:<34} {fn()}")
    except Exception as e: print(f"{label:<34} EXC {type(e).__name__}: {str(e)[:50]}")

def tcp(host, port):
    s = socket.socket(); s.settimeout(4)
    try:
        s.connect((host, port)); s.sendall(b"GET / HTTP/1.0\r\nHost: t\r\n\r\n")
        d = s.recv(64); return f"connected, {len(d)}B reply"
    finally: s.close()

def tls(host):
    s = socket.socket(); s.settimeout(6)
    w = ssl.create_default_context().wrap_socket(s, server_hostname=host)
    try:
        w.connect((host, 443)); w.sendall(f"GET / HTTP/1.0\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
        d = w.recv(120); return f"TLS ok, {d[:24]!r}"
    finally: w.close()

def udp_dns(server, name):
    q = b"\xab\xcd\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    for lbl in name.split(b"."): q += bytes([len(lbl)]) + lbl
    q += b"\x00\x00\x01\x00\x01"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(4)
    try:
        s.sendto(q, (server, 53)); d, _ = s.recvfrom(2048); return f"{len(d)}B answer"
    finally: s.close()

def ntp(server):
    p = bytearray(48); p[0] = 0x1B
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(4)
    try:
        s.sendto(p, (server, 123)); d, _ = s.recvfrom(1024); return f"NTP {len(d)}B"
    finally: s.close()

print("pod ip:", socket.gethostbyname(socket.gethostname()))
tag("tcp 1.1.1.1:443",        lambda: tcp("1.1.1.1", 443))
tag("tcp 1.1.1.1:12345",      lambda: tcp("1.1.1.1", 12345))
tag("udp dns 1.1.1.1 a.example.com", lambda: udp_dns("1.1.1.1", "a.example.com"))
tag("udp dns 8.8.8.8 b.example.com", lambda: udp_dns("8.8.8.8", "b.example.com"))
tag("udp ntp 162.159.200.1",  lambda: ntp("162.159.200.1"))
tag("tls api.ipify.org",      lambda: tls("api.ipify.org"))
PY

sleep 2
echo; echo "=== log after the known traffic ==="; getlog after

python3 - "$OUT/before.json" "$OUT/after.json" <<'PY'
import json, sys
def rows(p):
    try:
        d = json.load(open(p))
        return d['rows'] if isinstance(d, dict) else d
    except Exception as e:
        print("  cannot read", p, e); return []
before, after = rows(sys.argv[1]), rows(sys.argv[2])
seen = {r.get('__digest__') for r in before}
new = [r for r in after if r.get('__digest__') not in seen]
print(f"  rows before={len(before)} after={len(after)} NEW={len(new)}")
vlan = [r for r in new if str(r.get('src','')).startswith('10.10.31') or str(r.get('dst','')).startswith('10.10.31')]
print(f"  NEW rows touching 10.10.31.x: {len(vlan)}")
print("  %-6s %-14s %-6s %-22s %-24s %s" % ("act", "interface", "rule", "source", "dest", "proto"))
for r in vlan[:40]:
    print("  %-6s %-14s %-6s %-22s %-24s %s" % (
        r.get('action'), r.get('interface'), r.get('rulenr'),
        f"{r.get('src')}:{r.get('srcport')}", f"{r.get('dst')}:{r.get('dstport')}", r.get('protoname')))
print("\n  interfaces seen in new rows:", {r.get('interface') for r in new})
print("  reading: rows on wg2 = routed via Proton; rows on pppoe0 = left directly;")
print("           only outbound rows and no inbound = the provider is not answering.")
PY

echo; echo "cleanup:  kubectl -n $NAMESPACE delete pod $POD"
