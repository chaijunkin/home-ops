#!/usr/bin/env python3
"""Step 024 - For every rule found dead in step 023, decide WHY it is dead.

READ-ONLY.

A rule referencing a missing metric has three very different causes, and only the first is
harmless:
  a) LABEL false positive - the audit matched a label name (by (requested_model)) not a metric.
  b) RULE BUG - the exporter is up and healthy but the rule uses a wrong/renamed metric name,
     so the protection it advertises does not exist.
  c) EXPORTER ABSENT - nothing exposes that family at all: the whole alert group is decorative.

Also re-checks the service-stopped path, because `opnsense_services_status{name="crowdsec"} == 0`
is true right now while no OpnsenseServiceStopped alert is firing.
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

BASE = os.environ.get("PROM", "http://localhost:19090")
REPO = os.environ.get("REPO", "/Users/jkchai/Developer/PUBLIC/chaijunkin-home-ops")

# (rule file, the metric names step 023 flagged) -- filtered to families worth a verdict
CANDIDATES = {
    "smartctl-exporter": ["smartctl_device_temperature", "smartctl_device_smart_status",
                          "smartctl_device_status", "smartctl_device_critical_warning",
                          "smartctl_device_media_errors", "smartctl_device_available_spare_threshold",
                          "smartctl_device_interface_speed"],
    "volsync": ["volsync_volume_out_of_sync"],
    "cloudflared": ["cloudflared_tunnel_user_connections"],
    "autobrr": ["autobrr_irc_channel_monitored_total", "autobrr_irc_channel_enabled_total"],
    "dragonfly": ["dragonfly_used_memory_bytes", "dragonfly_memory_limit_bytes"],
    "litellm": ["litellm_deployment_failed_fallbacks_total",
                "litellm_deployment_successful_fallbacks_total", "litellm_model_name"],
}
# names step 023 flagged that are labels, not metrics -> excluded from the verdict
LABEL_FALSE_POSITIVES = {
    "requested_model", "exception_class", "exception_status", "fallback_model",
    "exported_namespace",
}


def q(path, **params):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def names():
    return set(q("/api/v1/label/__name__/values").get("data", []))


def series(metric):
    try:
        return q("/api/v1/query", query=metric).get("data", {}).get("result", [])
    except Exception as e:                                    # noqa: BLE001
        return []


def similar(prefix, live):
    return sorted(x for x in live if x.startswith(prefix))


def main():
    live = names()
    print("===== WHY is each rule dead? =====\n")
    for group, metrics in CANDIDATES.items():
        present = [m for m in metrics if m in live]
        missing = [m for m in metrics if m not in live]
        print("-- %s" % group)
        print("   flagged %d, present %d, missing %d" % (len(metrics), len(present), len(missing)))
        if not missing:
            print("   -> all present; step 023 was a false positive here\n")
            continue
        # is *any* family from this exporter live?
        prefixes = {m.split("_")[0] for m in missing}
        for p in prefixes:
            fam = similar(p + "_", live)
            print("   live families starting %r: %s" % (p, fam[:8] or "NONE"))
        # is the exporter's target up?
        try:
            rs = q("/api/v1/query", query='up{job=~".*%s.*"}' % p).get("data", {}).get("result", [])
            print("   up{job=~.*%s.*}: %s" % (p, [(r["metric"].get("job"), r["value"][1]) for r in rs] or "no target"))
        except Exception as e:                                # noqa: BLE001
            print("   up query failed:", e)
        print()

    print("===== the stopped-service path (crowdsec has been down for days) =====")
    for sel in ('opnsense_services_stopped_total', 'opnsense_services_status == 0',
                'ALERTS{alertname="OpnsenseServiceStopped"}'):
        rs = series(sel)
        if sel.startswith("ALERTS"):
            print("   %s -> %s" % (sel, [(r["metric"].get("alertstate"), r["metric"].get("name"))
                                         for r in rs] or "NO SERIES AT ALL (never pending)"))
        else:
            print("   %-40s -> %s" % (sel, [(r["metric"].get("name"), r["value"][1]) for r in rs][:8]))
    print("   series labels on opnsense_services_stopped_total:")
    for r in series("opnsense_services_stopped_total"):
        print("     ", {k: v for k, v in r["metric"].items()
                        if k in ("name", "service_name", "instance")}, "=", r["value"][1])

    print("\n===== the rule actually deployed in the cluster (vs Git) =====")
    out = subprocess.run(["kubectl", "-n", "observability", "get", "prometheusrule",
                          "-o", "json"], capture_output=True, text=True)
    try:
        doc = json.loads(out.stdout)
    except Exception:                                         # noqa: BLE001
        print("   could not read prometheusrules:", out.stderr[:200])
        return 1
    for item in doc.get("items", []):
        nm = item["metadata"]["name"]
        if "opnsense" not in nm and "smartctl" not in nm and "volsync" not in nm:
            continue
        print("  %s" % nm)
        for g in item["spec"].get("groups", []):
            for r in g.get("rules", []):
                expr = " ".join((r.get("expr") or "").split())
                print("     %-42s %s" % (r.get("alert") or r.get("record"), expr[:96]))

    print("\n===== is anything else alerting that nobody is reading? (7d firing-hours) =====")
    try:
        rs = q("/api/v1/query", query='count by (alertname) (ALERTS{alertstate="firing"})'
               ).get("data", {}).get("result", [])
        for r in sorted(rs, key=lambda x: -int(float(x["value"][1]))):
            print("   %-38s %s series firing now" % (r["metric"].get("alertname"), r["value"][1]))
    except Exception as e:                                    # noqa: BLE001
        print("   ", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
