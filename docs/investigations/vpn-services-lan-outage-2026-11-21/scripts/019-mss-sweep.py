#!/usr/bin/env python3
"""Step 019 helper: MSS sweep to locate the PMTU blackhole on the WireGuard exit.

Runs INSIDE a VLAN-31 pod (Linux, python3) via `kubectl exec -i ... python3 -`.
For each candidate MSS we announce that segment size in the TCP handshake, then try a real
HTTPS request. A path with a PMTU blackhole hands back the SYN/SYN-ACK (64 B, fits anywhere)
and then silently discards anything with a payload, so the pass/fail boundary of this sweep
*is* the usable MTU of the tunnel.

Read-only: outbound HTTPS GET only, nothing is written anywhere.
"""
import socket
import ssl
import sys

HOST = "api.ipify.org"
CANDIDATES = [1460, 1452, 1440, 1436, 1420, 1400, 1380, 1360, 1340, 1280, 1220, 1000]

print(f"  probing {HOST}:443 from {'.'.join(socket.gethostbyname(socket.gethostname()).split('.')[:3])}.x")
print("  MSS    verdict        detail")
works = []
for mss in CANDIDATES:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(8)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_MAXSEG, mss)
        ctx = ssl.create_default_context()
        w = ctx.wrap_socket(s, server_hostname=HOST)
        w.connect((HOST, 443))
        req = f"GET / HTTP/1.0\r\nHost: {HOST}\r\nUser-Agent: mss-sweep\r\nConnection: close\r\n\r\n"
        w.sendall(req.encode())
        body = b""
        while len(body) < 2048:
            chunk = w.recv(1024)
            if not chunk:
                break
            body += chunk
        w.close()
        text = body.decode("utf8", "replace")
        if "HTTP/1." in text:
            pub = text.split("\r\n\r\n", 1)[-1].strip()[:40]
            print(f"  {mss:<6} PASS           egress IP={pub}")
            works.append(mss)
        else:
            print(f"  {mss:<6} FAIL           short reply {len(body)} B")
    except Exception as exc:  # noqa: BLE001 - we want every failure mode visible
        print(f"  {mss:<6} FAIL           {type(exc).__name__}: {str(exc)[:56]}")

if works:
    best = max(works)
    print(f"\n  largest working MSS = {best}  ->  tunnel MTU = {best + 40}")
    print(f"  set the OPNsense WireGuard interface MTU to {best + 40},")
    print(f"  or clamp MSS to {best} on the VLAN-31 -> VPN forward rules.")
else:
    print("\n  no MSS worked: the payload drop is not a PMTU problem, it is upstream/provider-side.")
sys.exit(0)
