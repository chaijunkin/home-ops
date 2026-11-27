#!/usr/bin/env python3
"""Step 040 - SpeedtestExporterAbsent: staleness arithmetic (READ-ONLY).

The rule is

    absent(up{job=~".*speedtest-exporter.*"} == 1)   for: 75m

and the ServiceMonitor scrapes every 60m. Prometheus drops a series from *instant* queries ~5 minutes
after its last sample (the staleness lookback), so `up == 1` is only selectable for ~5 of every 60
minutes. For the remaining ~55 minutes absent() is true and the alert sits pending. Whether that ever
reaches 75m depends on nothing but timing, which is why step 038/039 saw it fire while the pod was
genuinely fine.

Steps 038/039 could not answer "is data actually there" because /api/v1/series, an instant query, and a
3600s-step range query all inherit that same 5-minute lookback. Everything below is lookback-immune:
count_over_time / min_over_time / a 60s-step range that shows the exact sample times.
"""

import json
import urllib.parse
import urllib.request

BASE = "http://localhost:9091"
JOB_RE = ".*speedtest-exporter.*"


def api(path, **params):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            return json.load(r)
    except Exception as exc:                                    # noqa: BLE001
        return {"_error": str(exc)}


def q(expr):
    d = api("/api/v1/query", query=expr)
    if "_error" in d:
        print(f"     ERROR {d['_error']}")
        return
    rows = d.get("data", {}).get("result", [])
    if not rows:
        print("     (empty - the expression yields no series right now)")
    for r in rows:
        print(f"     {r['value'][1]:>16}  {json.dumps(r['metric'])[:100]}")


section = lambda t: print("\n" + "=" * 100 + f"\n{t}\n" + "=" * 100)  # noqa: E731

section("1. Are samples actually arriving? (count_over_time ignores the staleness lookback)")
for expr in [
    f'count_over_time(up{{job=~"{JOB_RE}"}}[24h])',
    f'min_over_time(up{{job=~"{JOB_RE}"}}[24h])',
    f'max_over_time(up{{job=~"{JOB_RE}"}}[24h])',
    f"count_over_time(speedtest_download_bits_per_second[{('24h')}])",
    "count_over_time(speedtest_up[24h])",
    "min_over_time(speedtest_up[24h])",
]:
    print(f"   {expr}")
    q(expr)

section("2. Exact sample times in the last 6h (60s step shows where the samples really land)")
import time  # noqa: E402

now = int(time.time())
d = api(
    "/api/v1/query_range",
    query=f'up{{job=~"{JOB_RE}"}}',
    start=str(now - 6 * 3600),
    end=str(now),
    step="300",
)
if "_error" in d:
    print("   ERROR:", d["_error"])
elif not d["data"]["result"]:
    print("   (no samples at all in 6h)")
else:
    for s in d["data"]["result"]:
        for ts, val in s["values"]:
            print(f"     {time.strftime('%m-%d %H:%M:%S', time.gmtime(float(ts)))}  up={val}")

section("3. Current alert state and duty cycle over 24h")
for expr in [
    'ALERTS{alertname=~"Speedtest.*"}',
    'count_over_time(ALERTS{alertname="SpeedtestExporterAbsent",alertstate="firing"}[24h])',
    'count_over_time(ALERTS{alertname="SpeedtestExporterAbsent",alertstate="pending"}[24h])',
    "count_over_time(ALERTS{alertname='Watchdog'}[24h])",
]:
    print(f"   {expr}")
    q(expr)

section("4. The fix, evaluated live: absent_over_time over >2 scrape intervals")
print("   a window of 130m always contains at least two 60m-scrape samples, so it is empty while")
print("   healthy and only turns 1 when the target has truly gone quiet.\n")
for expr in [
    f'absent_over_time(up{{job=~"{JOB_RE}"}}[130m])',
    f'absent_over_time(up{{job=~"{JOB_RE}"}}[65m])',
    'absent_over_time(speedtest_download_bits_per_second[130m])',
    "absent_over_time(speedtest_up[130m])",
    "absent_over_time(opnsense_gateways_status[10m])",
    "absent_over_time(probe_success{job=~'probe/observability/vpn-.*'}[90m])",
]:
    print(f"   {expr}")
    q(expr)

section("5. Would the OTHER speedtest rules see data? (avg_over_time[4h] on 60m samples)")
for expr in [
    f'avg_over_time(speedtest_download_bits_per_second{{job=~"{JOB_RE}"}}[4h])',
    f'avg_over_time(speedtest_upload_bits_per_second{{job=~"{JOB_RE}"}}[4h])',
    f'avg_over_time(speedtest_ping_latency_milliseconds{{job=~"{JOB_RE}"}}[4h])',
]:
    print(f"   {expr}")
    q(expr)

section("6. Rule health (step 039 crashed here: groups have no 'namespace' key)")
d = api("/api/v1/rules")
if "_error" in d:
    print("   ERROR:", d["_error"])
    raise SystemExit(1)
groups = d["data"]["groups"]
print("   group keys sample:", sorted(groups[0].keys()) if groups else "none")
want = {
    "SpeedtestExporterAbsent",
    "VpnTunnelUpButNoReturn",
    "VpnProbeFailed",
    "VpnEgressProbesAbsent",
    "OpnsenseServiceStopped",
    "OpnsenseGatewayMonitoringDisabled",
    "VolSyncVolumeOutOfSync",
}
found = {}
for g in groups:
    for r in g.get("rules", []):
        if r["name"] in want:
            found[r["name"]] = (g.get("file", g.get("name")), r)
for name in sorted(want):
    if name not in found:
        print(f"   {name:32s} NOT DEPLOYED"
              + ("  <- correct, volsync rules are gone" if "VolSync" in name else "  <- CHECK"))
        continue
    src, r = found[name]
    print(f"   {name:32s} health={r.get('health', '?'):7s} state={r.get('state', '-'):8s} "
          f"for={r.get('for', '-'):6s} interval={r.get('interval', '-')}")
    if r.get("lastError"):
        print(f"     lastError: {r['lastError'][:140]}")
