#!/usr/bin/env bash
# Step 013 - "not just the alert: my Mac is slow, the whole internet is slow. Why?"
#
# READ-ONLY. "Everything is slow everywhere" has exactly three possible causes:
#   A. something inside the house is eating the link   (a saturating flow + bufferbloat)
#   B. the access link / last mile is impaired         (loss, latency, a cap)
#   C. name resolution is slow                         (DNS feels like "the internet is slow")
# This measures all three from two vantage points: the Mac (Wi-Fi) and the cluster (wired).
set -uo pipefail
NAMESPACE=observability
PROM_POD=prometheus-kube-prometheus-stack-0
PORT=19090
FW=192.168.1.1
BRAS=210.186.239.254
HERE=$(cd "$(dirname "$0")" && pwd)
FMT="$HERE/lib-fmt.py"

echo "now: $(date '+%Y-%m-%d %H:%M:%S %Z')  /  $(date -u '+%H:%M:%S UTC')"

echo
echo "=== A. IS A FLOW EATING THE LINK? (pppoe0 utilisation vs its ~912 Mbps capacity) ==="
kubectl -n "$NAMESPACE" port-forward "pod/$PROM_POD" "$PORT:9090" >/dev/null 2>&1 &
PF=$!; trap 'kill $PF 2>/dev/null' EXIT; sleep 5
q(){ curl -sG --max-time 30 "http://localhost:$PORT/api/v1/query" --data-urlencode "query=$1" \
   | python3 "$FMT" instant; }
rng(){ curl -sG --max-time 45 "http://localhost:$PORT/api/v1/query_range" --data-urlencode "query=$1" \
   --data-urlencode "start=$(( $(date +%s) - ${2:-12}*3600 ))" --data-urlencode "end=$(date +%s)" --data-urlencode "step=${3:-900}" \
   | python3 "$FMT" range; }
echo "-- pppoe0 receive (download) now, Mbps"
q 'rate(node_network_receive_bytes_total{device="pppoe0"}[5m])*8/1e6'
echo "-- pppoe0 transmit (upload) now, Mbps"
q 'rate(node_network_transmit_bytes_total{device="pppoe0"}[5m])*8/1e6'
echo "-- peak in/out over 12 h, Mbps  (near ~912 down would mean self-inflicted congestion)"
q 'max_over_time(rate(node_network_receive_bytes_total{device="pppoe0"}[5m])[12h:1m])*8/1e6'
q 'max_over_time((rate(node_network_transmit_bytes_total{device="pppoe0"}[5m]))[12h:1m])*8/1e6'
echo "-- hourly download profile, 12 h (Mbps):"
rng 'rate(node_network_receive_bytes_total{device="pppoe0"}[15m])*8/1e6' 12 900

echo
echo "=== B. WIRED vantage inside the cluster: blackbox ICMP probes to the public internet ==="
echo "-- probe duration to public targets, last 6 h (seconds). Healthy ~0.005-0.02"
rng 'probe_icmp_duration_seconds' 6 1200
echo "-- probe_success over 6 h (0 = that probe failed outright)"
rng 'probe_success' 6 1200

echo
echo "=== C. DNS - is name resolution the thing that feels like slowness? ==="
echo "-- full curl phase breakdown via the Mac's normal resolver (3 runs):"
for i in 1 2 3; do
  printf "   run %d: " "$i"
  curl -o /dev/null -sS --max-time 20 \
    -w 'dns=%{time_namelookup}s tcp=%{time_connect}s tls=%{time_appconnect}s ttfb=%{time_starttransfer}s\n' \
    "https://www.google.com" 2>&1 | sed 's/^/     /'
done
echo "-- per-query time, explicit resolvers (3 runs each):"
for r in 1.1.1.1 8.8.8.8; do
  printf "   via %-9s " "$r"
  for i in 1 2 3; do
    dig +time=2 +tries=1 @"$r" example.com A 2>/dev/null | awk '/Query time/{printf "%sms ", $4}'
  done
  echo
done
echo "-- what resolvers is the Mac actually using?"
scutil --dns 2>/dev/null | awk '/^resolver #1/{f=1} f&&/nameserver\[/{printf "   %s\n",$2} f&&/^resolver #2/{exit}'

echo
echo "=== D. MAC (Wi-Fi) -> each hop, 30 ICMP probes: where does loss begin? ==="
for h in "$FW" "$BRAS" 8.8.8.8 1.1.1.1; do
  printf "   %-17s " "$h"
  ping -c 30 -i 0.5 -t 4 "$h" 2>/dev/null | python3 -c "
import sys
ls=sys.stdin.read().splitlines()
loss=[l.split(',')[2].strip() for l in ls if 'packet loss' in l]
rt=[l.split('=')[1].strip() for l in ls if 'round-trip' in l]
print((loss[0] if loss else 'no reply'), '|', (rt[0] if rt else '-'), 'ms')
"
done

echo
echo "=== F. MAC link quality (Wi-Fi): RSSI / noise / transmit rate ==="
if command -v networkQuality >/dev/null 2>&1; then
  networkQuality -s 2>&1 | sed 's/^/   /'
fi
AIR=/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport
if [ -x "$AIR" ]; then
  "$AIR" -I 2>/dev/null | awk '/agrRSSI|RSSI|noise|SSID|BSSID|txrate|MCS|channel/{print "  ", $0}'
else
  system_profiler SPAirPortDataType 2>/dev/null | awk '/Other Local Networks/{f=1} f&&/Channel|RSSI|Noise|Transmit Rate|Security/{print "  ", $1, $2, $3, $4} f&&/^$/{c++; if(c>2) exit}'
fi
echo "-- current interface + IP"
route -n get default 2>/dev/null | awk '/interface:|gateway:/{print "   ", $1, $2}'

echo
echo "=== G. ICMP RTT *distribution* - bimodal means multipath spraying, unimodal means congestion ==="
echo "-- 60 probes each; sorted raw RTTs. Two clusters (e.g. 5 ms and 135 ms) = two paths."
for h in "$BRAS" 8.8.8.8 1.1.1.1; do
  echo "   --- $h"
  ping -c 60 -i 0.25 -t 4 "$h" 2>/dev/null | python3 -c "
import sys, statistics as st
rt=[]
for l in sys.stdin:
    if 'time=' in l:
        try: rt.append(float(l.rsplit('time=',1)[1].split()[0]))
        except ValueError: pass
if len(rt) < 5:
    print('      too few replies (%d)' % len(rt)); raise SystemExit
rt.sort()
def pct(p): return rt[min(len(rt)-1, int(len(rt)*p))]
# gap detection: largest jump between consecutive sorted samples
gaps=[(rt[i+1]-rt[i], rt[i], rt[i+1]) for i in range(len(rt)-1)]
big, lo, hi = max(gaps)
lo_cluster=[x for x in rt if x <= rt[rt.index(hi)] ] if hi in rt else []
fast=len([x for x in rt if x < (lo+hi)/2]); slow=len(rt)-fast
print('      n=%d  loss=%.1f%%  min=%.1f p50=%.1f p90=%.1f max=%.1f' % (
      len(rt), (60-len(rt))/60*100, rt[0], pct(.5), pct(.9), rt[-1]))
print('      largest gap in sorted RTTs: %.1f ms  (%.1f -> %.1f ms)' % (big, lo, hi))
print('      clusters below/above that gap: %d / %d packets' % (fast, slow))
print('      fast mean=%s  slow mean=%s' % (
      ('%.1f' % st.mean([x for x in rt if x < (lo+hi)/2])) if fast else '-',
      ('%.1f' % st.mean([x for x in rt if x >= (lo+hi)/2])) if slow else '-'))
print('      sample sorted:', ' '.join('%.0f' % x for x in rt[:30]), '...')
"
done

echo
echo "=== H. TCP handshake RTT (ICMP may be deprioritised by the ISP; TCP is what your apps use) ==="
python3 - <<'PY'
import socket, time, statistics as st
for host, ip in (("speed.cloudflare.com","104.16.132.229"), ("Google DNS","1.1.1.1"), ("Google DNS2","8.8.8.8")):
    rt=[]; fails=0
    for _ in range(20):
        t0=time.perf_counter()
        s=socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(4)
        try:
            s.connect((ip,443)); rt.append((time.perf_counter()-t0)*1000)
        except OSError:
            fails+=1
        finally:
            s.close()
        time.sleep(0.15)
    if rt:
        rt.sort()
        print(f"   {host:<22} ({ip})  n={len(rt)} fail={fails}  min={rt[0]:.1f} p50={rt[len(rt)//2]:.1f} max={rt[-1]:.1f} ms")
    else:
        print(f"   {host:<22} ({ip})  all {fails} TCP connects failed")
PY

echo
echo "=== I. Reordering check - 30 probes, count out-of-order arrivals (multipath signature) ==="
python3 - <<'PY'
import subprocess, re, collections
for ip in ("8.8.8.8",):
    seq=[]
    out=subprocess.run(["ping","-c","30","-i","0.2","-t","4",ip],capture_output=True,text=True).stdout
    for l in out.splitlines():
        m=re.search(r"icmp_seq=(\d+).*time=([\d.]+)", l)
        if m: seq.append((int(m.group(1)), float(m.group(2))))
    if len(seq)<10:
        print("   too few replies"); raise SystemExit
    # ping prints in arrival order; a sequence gap means the reply arrived out of order
    arrived=[s for s,_ in seq]
    ooo=sum(1 for i in range(1,len(arrived)) if arrived[i] < arrived[i-1])
    missing=sorted(set(range(min(arrived),max(arrived)+1)) - set(arrived))
    print(f"   {ip}: n={len(arrived)} seqs={arrived[:12]}...")
    print(f"   out-of-order arrivals: {ooo}   missing seqs: {missing[:12]}")
    print("   (out-of-order + missing-that-then-reappear later = multipath reordering, not loss)")
PY

echo
echo "=== J. Reality check from the Mac: 3 x 25 MB downloads, same endpoint ==="
for i in 1 2 3; do
  printf "   run %d: " "$i"
  curl -o /dev/null -sS --max-time 40 -w 'dns=%{time_namelookup}s connect=%{time_connect}s tls=%{time_appconnect}s ttfb=%{time_starttransfer}s total=%{time_total}s speed=%{speed_download}s\n' \
    "https://speed.cloudflare.com/__down?bytes=25000000" 2>&1 \
    | python3 -c "
import sys,re
s=sys.stdin.read()
m=re.search(r'speed=([\d.]+)',s)
mbps=float(m.group(1))*8/1e6 if m else 0
print(s.strip(), '=> %.0f Mbps' % mbps)
"
done
