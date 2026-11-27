#!/usr/bin/env python3
"""Step 020 helper: is that "successful" TCP handshake real, and what payloads get through?

Runs INSIDE a VLAN-31 pod via `kubectl exec -i ... python3 -`. Read-only, outbound only.

Motivation: on 26 Nov the VPN probes showed a handshake that succeeded in 13 ms while every
payload died. Two explanations fit, and they need opposite fixes:
  (a) the exit works and only TLS-sized/larger payloads are being dropped, or
  (b) the handshake is answered by something that is not the real server (a middlebox, a local
      redirect, or a blackhole route that accepts everything), so nothing ever leaves.
Test 1 distinguishes them: a real internet path REFUSES closed ports. If closed ports also
"connect", the successes are fake. Tests 2-4 then measure which payload shapes still work.
"""
import socket
import struct
import time

def tcp_probe(host, port, timeout=5):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    t0 = time.perf_counter()
    try:
        s.connect((host, port))
        ms = (time.perf_counter() - t0) * 1000
        try:
            s.settimeout(2)
            s.sendall(b"\x00" * 16)
            data = s.recv(64)
            return f"CONNECT {ms:.0f}ms, reply {len(data)}B" if data else f"CONNECT {ms:.0f}ms, closed on read"
        except OSError as e:
            return f"CONNECT {ms:.0f}ms, no reply ({type(e).__name__})"
    except OSError as e:
        return f"REFUSED/UNREACH ({type(e).__name__})"
    finally:
        s.close()

print("TEST 1 - closed ports must REFUSE. If these 'connect', the path is fake.")
for host, port in (("1.1.1.1", 443), ("1.1.1.1", 81), ("1.1.1.1", 8701), ("1.1.1.1", 12345),
                   ("8.8.8.8", 443), ("8.8.8.8", 9999), ("9.9.9.9", 53)):
    print(f"   {host}:{port:<6} {tcp_probe(host, port)}")

def dns_udp(server, name=b"example.com", edns=False):
    tid = 0x1234
    q = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 1 if edns else 0)
    for label in name.split(b"."):
        q += bytes([len(label)]) + label
    q += b"\x00" + struct.pack(">HH", 1, 1)
    if edns:
        q += struct.pack(">HHIH", 0, 4112, 0, 0)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(5)
    t0 = time.perf_counter()
    try:
        s.sendto(q, (server, 53))
        data, _ = s.recvfrom(4096)
        return f"OK {(time.perf_counter()-t0)*1000:.0f}ms, {len(data)}B"
    except OSError as e:
        return f"FAIL {type(e).__name__}"
    finally:
        s.close()

print("\nTEST 2 - tiny UDP payload (DNS A query, ~90 B both ways)")
for r in ("1.1.1.1", "8.8.8.8", "9.9.9.9"):
    print(f"   {r:<12} small: {dns_udp(r)}     large-edns: {dns_udp(r, 'example.com', edns=True)}")

def dns_tcp(server, name=b"example.com"):
    q = struct.pack(">HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
    for label in name.split(b"."):
        q += bytes([len(label)]) + label
    q += b"\x00" + struct.pack(">HH", 1, 1)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect((server, 53))
        s.sendall(struct.pack(">H", len(q)) + q)
        hdr = s.recv(2)
        if len(hdr) < 2:
            return "connected, no length prefix"
        n = struct.unpack(">H", hdr)[0]
        body = s.recv(n)
        return f"OK, {2+len(body)}B answer"
    except OSError as e:
        return f"FAIL {type(e).__name__}"
    finally:
        s.close()

print("\nTEST 3 - tiny TCP payload (DNS over TCP, answer ~90 B)")
for r in ("9.9.9.9", "1.1.1.1"):
    print(f"   {r:<12} {dns_tcp(r)}")

def ntp(server):
    pkt = bytearray(48)
    pkt[0] = 0x1B
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(5)
    t0 = time.perf_counter()
    try:
        s.sendto(pkt, (server, 123))
        data, _ = s.recvfrom(1024)
        return f"OK {(time.perf_counter()-t0)*1000:.0f}ms, {len(data)}B"
    except OSError as e:
        return f"FAIL {type(e).__name__}"
    finally:
        s.close()

print("\nTEST 4 - fixed 48-byte UDP both ways (NTP)")
for r in ("162.159.200.1", "1.1.1.1"):
    print(f"   {r:<16} {ntp(r)}")

print("\nREAD THIS:")
print("   closed ports REFUSE + tiny payloads OK  -> the exit works; only larger payloads die")
print("   closed ports also 'connect'             -> nothing is leaving; the path is a blackhole")
print("   tiny payloads fail too                  -> return path is dead, handshakes are illusion")
