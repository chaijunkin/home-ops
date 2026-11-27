#!/usr/bin/env python3
"""Step 038 - Post-merge follow-ups (READ-ONLY).

Three things the first pass left unanswered:
  1. Why does the volsync-system Namespace still exist after Flux pruned everything inside it?
  2. SpeedtestExporterAbsent is FIRING while the pod is clearly Running and measuring hourly -
     is Prometheus still scraping it at all (no `up` series came back)?
  3. Which jobs are behind KubeJobFailed x4, and are the rules #2604/#2607/#2608 shipped healthy
     (including VolSyncVolumeOutOfSync now being gone)?

Step 037's probe query was also wrong: it filtered probe_success on job="blackbox-exporter-vpn",
which is the exporter's `up` label. The probe series carry job="probe/observability/vpn-*". Corrected
below rather than left as a silent miss.
"""
import json
import subprocess
import urllib.parse
import urllib.request

BASE = "http://localhost:9091"


def api(path, query=None):
    url = BASE + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            return json.load(r)
    except Exception as exc:                                    # noqa: BLE001
        return {"_error": str(exc)}


def q(expr):
    d = api("/api/v1/query", {"query": expr})
    if "_error" in d:
        return [("ERROR", d["_error"])]
    out = []
    for r in d.get("data", {}).get("result", []):
        m = r["metric"]
        lab = " ".join(f"{k}={m[k]}" for k in
                       ("alertname", "namespace", "job", "instance", "name", "peer_name", "severity")
                       if k in m)
        out.append((r["value"][1], lab))
    return out


def sh(*args):
    r = subprocess.run(args, capture_output=True, text=True)
    return (r.stdout or r.stderr).strip()


def section(t):
    print("\n" + "=" * 100 + f"\n{t}\n" + "=" * 100)


def main():
    section("1. The orphan volsync-system Namespace")
    ns = sh("kubectl", "get", "ns", "volsync-system", "-o", "yaml")
    keep = ("phase", "kustomize.toolkit.fluxcd.io", "kubectl.kubernetes.io/last-applied",
            "finalizers", "flux-config", "name:", "  labels:", "  annotations:")
    body = [ln for ln in ns.splitlines() if any(k in ln for k in keep)]
    print("\n".join("   " + ln for ln in body[:24]))
    print("\n   objects still inside:")
    print("   ", sh("kubectl", "get", "all,secret,cm,serviceaccount,netpol,role,rolebinding",
                    "-n", "volsync-system", "--no-headers") or "none")
    print("\n   does anything still own/label objects here (Flux owner refs)?")
    owners = sh("kubectl", "get", "serviceaccount,default", "-n", "volsync-system",
                "-o", "jsonpath={.metadata.ownerReferences} {.metadata.creationTimestamp}")
    print("   ", owners or "none")

    section("2. Is Prometheus still scraping speedtest-exporter?")
    d = api("/api/v1/targets", {"state": "any"})
    if "_error" in d:
        print("   ERROR:", d["_error"])
    else:
        rows = d["data"].get("activeTargets", []) + d["data"].get("droppedTargets", [])
        hits = [t for t in rows if "speedtest" in json.dumps(t.get("labels", {}))
                or "speedtest" in t.get("discoveredLabels", {}).get("__address__", "")]
        print(f"   targets mentioning speedtest: {len(hits)}")
        for t in hits[:6]:
            print(f"     job={t.get('labels', {}).get('job')} health={t.get('health')} "
                  f"lastError={(t.get('lastError') or '-')[:110]}")
            print(f"       scrapeUrl={t.get('scrapeUrl')} lastScrape={t.get('lastScrape')} "
                  f"lastDuration={t.get('lastScrapeDuration')} samples={t.get('lastSamplesScraped')}")
        print("\n   how many targets are unhealthy overall:")
        bad = [t for t in d["data"].get("activeTargets", []) if t.get("health") != "up"]
        print(f"     {len(bad)} unhealthy")
        for t in bad[:10]:
            print(f"       {t.get('labels', {}).get('job')} {t.get('health')} "
                  f"{(t.get('lastError') or '')[:100]}")
    print("\n   speedtest metric presence over the last 3h (60m scrape interval):")
    for expr in ['count(speedtest_download_bits_per_second)',
                 'timestamp(speedtest_download_bits_per_second)',
                 'up{job=~".*speedtest.*"}',
                 'absent(speedtest_download_bits_per_second)']:
        for val, lab in q(expr):
            print(f"     {expr:52s} -> {val}  {lab}")

    section("3. Alerts that need a name attached")
    for alert in ("KubeJobFailed", "KubeHpaMaxedOut"):
        print(f"   {alert}:")
        for val, lab in q(f'ALERTS{{alertname="{alert}"}}'):
            print(f"     {val}  {lab}")
        print("     job names (24h):")
        for val, lab in q('count by (job_name) (kube_job_status_failed{job_status_failed="1"})'):
            print(f"       {val}  {lab}")

    section("4. Deployed rule health (what #2604/#2607/#2608 shipped + the deleted one)")
    d = api("/api/v1/rules")
    if "_error" in d:
        print("   ERROR:", d["_error"])
        return 1
    want = {"VpnTunnelUpButNoReturn", "VpnProbeFailed", "OpnsenseServiceStopped",
            "CloudflareTunnelOffline", "DragonflyHighMemoryUsage", "AutobrrNetworkUnmonitored",
            "OpnsenseApiExporterAbsent", "VpnEgressProbesAbsent", "VpnEgressTunnelAbsent",
            "OpnsenseExporterEndpointErrors", "SpeedtestExporterAbsent", "VolSyncVolumeOutOfSync"}
    found = {}
    for g in d["data"]["groups"]:
        for r in g.get("rules", []):
            if r["name"] in want:
                found[r["name"]] = (g["namespace"], g["group"], r)
    for name in sorted(want):
        if name not in found:
            verdict = "NOT DEPLOYED" + (" - correct, volsync alert rules are gone"
                                        if name == "VolSyncVolumeOutOfSync" else " - CHECK")
            print(f"   {name:32s} {verdict}")
            continue
        ns, grp, r = found[name]
        print(f"   {name:32s} health={r.get('health'):7s} state={r.get('state','-'):9s} "
              f"for={r.get('for','-')} group={ns}/{grp}")
        if r.get("lastError"):
            print(f"     lastError: {r['lastError'][:150]}")

    section("5. Corrected probe query (step 037 used the wrong job label)")
    for expr in ['probe_success{job=~"probe/observability/vpn-.*"}',
                 'probe_success',
                 'count by (job) (probe_success)']:
        rows = q(expr)
        print(f"   {expr}")
        if not rows:
            print("     (no series)")
        for val, lab in rows[:12]:
            print(f"     {val:>6}  {lab}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
