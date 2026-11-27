#!/usr/bin/env python3
"""Step 039 - Why SpeedtestExporterAbsent fires while the exporter is healthy (READ-ONLY).

Step 038 showed the paradox: target health=up, lastScrape 19:27:55Z, lastScrapeDuration 22.6s, and the
pod logs a completed test at 19:28:18Z - yet absent(speedtest_download_bits_per_second) == 1 and
count(speedtest_download_bits_per_second) returns nothing at all.

Two candidate explanations, and the queries below separate them:
  A. the series name changed (exporter image bump) -> old names genuinely gone, rule + dashboards stale
  B. the exporter exposes results only for an instant / the scrape races the test -> rule design flaw
The scrape duration (22.6s) plus the pod's own timestamp (test finished 23s AFTER the scrape started)
already points at B; enumerate every speedtest* series and their staleness to prove it.
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


def q(expr):
    d = api("/api/v1/query", query=expr)
    if "_error" in d:
        print(f"     ERROR {d['_error']}")
        return
    rows = d.get("data", {}).get("result", [])
    if not rows:
        print("     (no series)")
    for r in rows:
        print(f"     {r['value'][1]:>16}  {json.dumps(r['metric'])[:120]}")


section = lambda t: print("\n" + "=" * 100 + f"\n{t}\n" + "=" * 100)  # noqa: E731

section("1. Every speedtest* series Prometheus has right now")
d = api("/api/v1/series", match='__name__=~"speedtest.*"')
names = sorted({s.get("__name__", "?") for s in d.get("data", [])}) if "data" in d else []
print(f"   /api/v1/series -> {len(names)} distinct names: {names}")
print("   __name__ enumeration (label values):")
lv = api("/api/v1/label/__name__/values")
allnames = [n for n in lv.get("data", []) if "speedtest" in n.lower()] if "data" in lv else []
print(f"     {allnames if allnames else 'NONE - no speedtest metric exists in the TSDB'}")

section("2. The rule as deployed vs what the exporter actually serves")
print("   instant queries:")
for expr in ['count({__name__=~"speedtest.*"})',
             'absent(speedtest_download_bits_per_second)',
             'up{job="speedtest-exporter"}',
             'timestamp(up{job="speedtest-exporter"})']:
    print(f"   {expr}")
    q(expr)

section("3. Did the series exist earlier today? (5-day range, presence per 6h)")
d = api("/api/v1/query_range", query='count({__name__=~"speedtest.*"})', start="", step="")
# build a proper range
import time
now = int(time.time())
d = api("/api/v1/query_range", query='count({__name__=~"speedtest.*"})',
        start=str(now - 5 * 86400), end=str(now), step="3600")
if "data" in d and d["data"]["result"]:
    for pt in d["data"]["result"][0]["values"]:
        print(f"     {time.strftime('%m-%d %H:%M', time.localtime(int(float(pt[0]))))}  series={pt[1]}")
else:
    print("   (no range data - the metric family has not existed in the last 5 days)")

section("4. What the exporter serves directly (no Prometheus in the path)")
print("   pod log line format + last 3 tests already captured in step 037 output.")
d = api("/api/v1/targets", state="any")
if "data" in d:
    for t in d["data"].get("activeTargets", []):
        if t.get("labels", {}).get("job") == "speedtest-exporter":
            print(f"   scrapeUrl          = {t.get('scrapeUrl')}")
            print(f"   lastScrape         = {t.get('lastScrape')}")
            print(f"   lastScrapeDuration = {t.get('lastScrapeDuration')}")
            print(f"   lastValue          = {t.get('lastValue')}")
            print(f"   labels             = {json.dumps(t.get('labels'))}")

section("5. Which jobs are failing (KubeJobFailed x4)")
for expr in ['kube_job_status_failed == 1', 'kube_job_failed == 1',
             'max by (namespace,job_name) (kube_job_status_failed)']:
    print(f"   {expr}")
    q(expr)

section("6. Rule health for everything this investigation shipped (retry, long timeout)")
d = api("/api/v1/rules")
if "_error" in d:
    print("   ERROR:", d["_error"])
    raise SystemExit(1)
want = {"VpnTunnelUpButNoReturn", "VpnProbeFailed", "OpnsenseServiceStopped", "CloudflareTunnelOffline",
        "DragonflyHighMemoryUsage", "AutobrrNetworkUnmonitored", "OpnsenseApiExporterAbsent",
        "VpnEgressProbesAbsent", "VpnEgressTunnelAbsent", "OpnsenseExporterEndpointErrors",
        "SpeedtestExporterAbsent", "VolSyncVolumeOutOfSync"}
found = {}
for g in d["data"]["groups"]:
    for r in g.get("rules", []):
        if r["name"] in want:
            found[r["name"]] = (g["namespace"], g["group"], r)
for name in sorted(want):
    if name not in found:
        print(f"   {name:32s} NOT DEPLOYED" +
              ("  <- correct: volsync rules are gone with #2608" if "VolSync" in name else "  <- CHECK"))
        continue
    ns, grp, r = found[name]
    print(f"   {name:32s} health={r.get('health'):7s} state={r.get('state','-'):8s} "
          f"for={r.get('for','-'):6s} group={ns}/{grp}")
    if r.get("lastError"):
        print(f"     lastError: {r['lastError'][:140]}")
