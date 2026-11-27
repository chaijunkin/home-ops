#!/usr/bin/env python3
"""Step 041 - Audit every bare absent() rule against its scrape interval (READ-ONLY).

Step 040 proved the mechanism on one rule; this checks whether it applies to the others, and checks
the selectors shipped in #2604 for the opposite failure mode: a bare absent() whose label selector
matches nothing is permanently true, i.e. an alert that has already been silently wrong since deploy.

Selectors under test (from prometheusrule-monitoring-coverage.yaml):
    probe_success{service="blackbox-exporter-vpn"}
    opnsense_wireguard_peer_last_handshake_seconds{device="wg2"}
Step 038 established probe series carry job="probe/observability/vpn-*", so `service=` deserves proof.

Replacement for SpeedtestExporterAbsent is evaluated in three shapes: healthy (must be empty),
target gone (must be 1), target scraped but always failing (must be 1). The two arms are needed
because absent_over_time() cannot see a target that answers with up=0, and max_over_time() cannot
see a target that stopped producing samples.
"""

import json
import urllib.parse
import urllib.request

BASE = "http://localhost:9091"


def api(path, **params):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            return json.load(r)
    except Exception as exc:                                    # noqa: BLE001
        return {"_error": str(exc)}


def rows(expr):
    d = api("/api/v1/query", query=expr)
    if "_error" in d:
        return None
    return [(r["value"][1], r["metric"]) for r in d.get("data", {}).get("result", [])]


def show(label, expr, want):
    got = rows(expr)
    if got is None:
        print(f"   {label:34s} ERROR")
        return
    verdict = "OK " if (bool(got) == want) else "!! "
    val = got[0][0] if got else "-"
    print(f"   {verdict}{label:32s} present={bool(got)!s:5s} value={val:>10}  "
          f"(expected present={want!s})")
    for _, m in got[:2]:
        print(f"        {json.dumps(m)[:130]}")


section = lambda t: print("\n" + "=" * 100 + f"\n{t}\n" + "=" * 100)  # noqa: E731

section("1. #2604 coverage selectors - does each selector match a live series?")
print("   (bare absent() on a selector that matches nothing = permanently-true critical alert)\n")
show("probe_success{service=...}", 'probe_success{service="blackbox-exporter-vpn"}', True)
show("wireguard peer {device=\"wg2\"}",
     'opnsense_wireguard_peer_last_handshake_seconds{device="wg2"}', True)
show("up{job=\"opnsense-exporter\"}", 'up{job="opnsense-exporter"}', True)
print("\n   what labels the probe series really carry:")
for v, m in (rows('probe_success') or [])[:8]:
    print(f"     {v:>5}  {json.dumps(m)[:135]}")

section("2. The two coverage rules' current live state (already in 040 s6, restated with history)")
for expr in [
    'count_over_time(ALERTS{alertname="VpnEgressProbesAbsent"}[24h])',
    'count_over_time(ALERTS{alertname="VpnEgressTunnelAbsent"}[24h])',
    'ALERTS{alertname="VpnEgressProbesAbsent",alertstate="firing"}',
    'ALERTS{alertname="VpnEgressTunnelAbsent",alertstate="firing"}',
]:
    got = rows(expr) or []
    print(f"   {expr}")
    if not got:
        print("     (empty)")
    for v, m in got[:4]:
        print(f"     {v:>10}  {json.dumps(m)[:120]}")

section("3. Scrape interval per job (the number absent()+for: must be compared against)")
d = api("/api/v1/targets", state="active")
jobs = {}
if "data" in d:
    for t in d["data"].get("activeTargets", []):
        job = t.get("labels", {}).get("job", "?")
        gi = t.get("discoveredLabels", {}).get("__metrics_path__", "")
        interval = t.get("scrapeInterval") or t.get("labels", {}).get("interval") or "?"
        jobs.setdefault(job, [0, interval, gi])[0] += 1
for job in sorted(jobs):
    if any(k in job for k in ("speedtest", "opnsense", "nut", "cert-manager", "blackbox",
                              "smartctl", "node-exporter")):
        n, interval, path = jobs[job]
        print(f"   {job:34s} targets={n:2d} interval={interval} path={path}")
if not jobs:
    print("   ERROR: targets endpoint unavailable:", d.get("_error"))

section("4. Replacement expression, three shapes")
print("   arm1 = absent_over_time(up[130m])            -> target stopped producing samples")
print("   arm2 = max_over_time(up[130m]) == 0          -> every scrape in the window failed\n")
HEALTHY = 'absent_over_time(up{job=~".*speedtest-exporter.*"}[130m]) == 1 or ' \
          'max_over_time(up{job=~".*speedtest-exporter.*"}[130m]) == 0'
GONE = 'absent_over_time(up{job=~".*speedtest-exporter-nonexistent.*"}[130m]) == 1 or ' \
       'max_over_time(up{job=~".*speedtest-exporter-nonexistent.*"}[130m]) == 0'
print("   healthy exporter (must be EMPTY):")
got = rows(HEALTHY) or []
print(f"     present={bool(got)}  -> {'OK' if not got else '!! would false-positive'}")
print("\n   target gone entirely (must be 1):")
got = rows(GONE) or []
print(f"     present={bool(got)} value={got[0][0] if got else '-'}  "
      f"-> {'OK' if got and got[0][0] == '1' else '!! would miss a real outage'}")
print("\n   arm2 alone against live data (must be EMPTY while up=1):")
got = rows('max_over_time(up{job=~".*speedtest-exporter.*"}[130m]) == 0') or []
print(f"     present={bool(got)}  -> {'OK' if not got else '!! firing on a healthy target'}")

section("5. Sanity: the same arithmetic for the fast-scraped rules left alone")
for expr, want in [
    ('absent_over_time(up{job="opnsense-exporter"}[10m])', False),
    ('absent_over_time(probe_success{job=~"probe/observability/vpn-.*"}[10m])', False),
    ('absent_over_time(node_boot_time_seconds[10m])', False),
]:
    got = rows(expr) or []
    print(f"   {'OK ' if bool(got) == want else '!! '}{expr:70s} present={bool(got)}")
