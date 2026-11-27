#!/usr/bin/env python3
"""Step 023 - Alerting coverage audit: find rules that can never fire, and gaps.

READ-ONLY. Reads rule manifests from the repo and queries Prometheus (needs a
port-forward on 19090, started by the caller).

Answers two different questions that are easy to conflate:
  1. DEAD RULES  - a rule whose expression references a metric that does not exist in
     Prometheus can never fire, no matter what happens. These look identical to "working,
     just healthy" in the UI, so they are invisible unless audited. (Found 2 this way: the
     speedtest thresholds compared bit/s against Mbps.)
  2. GAPS        - conditions this incident proved real that no rule covers, checked against
     the live metric inventory rather than guessed.

No pyyaml on this host's system python, so rule bodies are extracted with a regex over the
`expr:` keys instead of a YAML parse.
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

PROM_FUNCS = set("""abs absent absent_over_time avg avg_over_time bottomk by ceil changes clamp_max
clamp_min count count_over_time day_of_month day_of_week days_in_month delta deriv deworm_exp destip drop
exp floor group group_left group_right histogram_avg histogram_count histogram_fraction histogram_quantile
histogram_stddev histogram_sum holt_winters hour idelta increase info instant_query ip bcontains infinite
keep_labels label_join label_replace last_over_time le ln log2 log10 max max_over_time meta_metadata min
min_over_time month pi predict_linear present_over_time quantile quantile_over_time rate resets
round scalar sgn sin sort sort_desc stddev stddev_over_time sum sum_over_time time timestamp topk vector
year avg_abs_over_time mad_over_time step_info histogram_subset_labels histogram_mad_over_time
info_over_time sanitize_label_name""".split())
PROM_KEYWORDS = {"on", "ignoring", "bool", "offset", "and", "or", "unless", "by", "without",
                 "keep_common", "start", "end", "step", "query", "true", "false", "nan", "inf"}


def q(path, **params):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def live_metrics():
    names = set()
    d = q("/api/v1/label/__name__/values")
    names.update(d.get("data", []))
    return names


def rule_files():
    out = subprocess.run(["grep", "-rl", "-E", r"^\s*(expr:|rules:)", REPO + "/kubernetes/apps",
                          "--include=*.yaml"], capture_output=True, text=True).stdout
    return sorted(p for p in out.splitlines() if "prometheusrule" in p or "helmrelease" in p)


def extract_rules(path):
    """Yield (alert_or_record_name, expr) pairs from one manifest."""
    text = open(path).read()
    lines = text.split("\n")
    current = None
    found = []
    name = None
    for i, line in enumerate(lines):
        m = re.search(r"(?:^|\s)(?:alert|record):\s*(\S+)", line)
        if m:
            name = m.group(1)
        me = re.search(r"^\s*expr:\s*(.*)$", line)
        if me:
            inline = me.group(1).strip()
            indent = len(line) - len(line.lstrip())
            body = []
            if inline.startswith("|") or inline == "":
                for nxt in lines[i + 1:]:
                    if nxt.strip() == "" or (len(nxt) - len(nxt.lstrip())) > indent:
                        body.append(nxt.strip())
                    else:
                        break
            else:
                body = [inline]
            expr = " ".join(x for x in body if x)
            found.append((name or "(unnamed@%d)" % (i + 1), expr))
    return found


def metrics_in(expr):
    """Metric-name candidates: selectors first, then bare identifiers."""
    cands = set(re.findall(r"([a-zA-Z_:][a-zA-Z0-9_:]*)\s*\{", expr))
    stripped = re.sub(r"\{[^{}]*\}", "{}", expr)
    for tok in re.findall(r"[a-zA-Z_:][a-zA-Z0-9_:]*", stripped):
        if "__name__" in tok:
            continue
        if tok in PROM_FUNCS or tok in PROM_KEYWORDS:
            continue
        if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", tok) and "_" in tok:
            cands.add(tok)
        if re.fullmatch(r"[a-zA-Z_:][a-zA-Z0-9_]*", tok) and ":" in tok:
            cands.add(tok)
    # templating leftovers and pure numbers are noise
    return {c for c in cands if "$" not in c and not c.isdigit()}


def main():
    try:
        live = live_metrics()
    except Exception as e:                                    # noqa: BLE001
        print("!! cannot reach Prometheus at %s (%s) - start the port-forward" % (BASE, e))
        return 2
    print("live metric names in Prometheus: %d" % len(live))

    dead = {}
    total = 0
    for f in rule_files():
        for name, expr in extract_rules(f):
            if not expr:
                continue
            total += 1
            missing = sorted(m for m in metrics_in(expr) if m not in live)
            if missing:
                dead.setdefault(os.path.relpath(f, REPO), []).append((name, missing))

    print("\n===== 1. DEAD RULES: rules referencing metrics that do not exist (%d/%d rules) ====="
          % (sum(len(v) for v in dead.values()), total))
    if not dead:
        print("   none - every rule's metrics currently have a series")
    for f, rows in dead.items():
        print("  %s" % f)
        for name, missing in rows:
            print("     %-34s missing: %s" % (name, ", ".join(missing)))

    print("\n===== 2. LIVE SERIES FOR CANDIDATE-ALERT METRICS =====")
    probes = [
        ("pf state pressure", "opnsense_firewall_states"),
        ("state total/max", "opnsense_firewall_state_max"),
        ("service down flag", "opnsense_services_status"),
        ("stopped counter", "opnsense_services_stopped_total"),
        ("wg peer status", "opnsense_wireguard_peer_status"),
        ("wireless/ups etc", "opnsense_ups"),
    ]
    d = q("/api/v1/label/__name__/values")
    existing = d.get("data", [])
    print("   all opnsense_* metric families exposed by the exporter:")
    for n in sorted(x for x in existing if x.startswith("opnsense")):
        print("     ", n)

    print("\n   what is stopped on the firewall right now:")
    for sel in ('opnsense_services_status == 0', 'opnsense_services_stopped_total'):
        try:
            rs = q("/api/v1/query", query=sel).get("data", {}).get("result", [])
            print("     %-40s -> %s" % (sel, [r["metric"].get("name") or r["metric"] for r in rs][:6]))
        except Exception as e:                                # noqa: BLE001
            print("     %-40s -> %s" % (sel, e))

    print("\n   which jobs are failing (unattended failures):")
    try:
        rs = q("/api/v1/query", query='ALERTS{alertname="KubeJobFailed",alertstate="firing"}'
               ).get("data", {}).get("result", [])
        for r in rs:
            print("     job=%s ns=%s" % (r["metric"].get("job_name") or r["metric"].get("job"),
                                         r["metric"].get("namespace")))
    except Exception as e:                                    # noqa: BLE001
        print("     ", e)

    print("\n   handshake age per wireguard peer (is a 'peer unreachable' alert safe?):")
    try:
        rs = q("/api/v1/query", query="time() - opnsense_wireguard_peer_last_handshake_seconds"
               ).get("data", {}).get("result", [])
        for r in rs:
            m = r["metric"]
            print("     device=%-4s peer=%-26s age=%.0f s" %
                  (m.get("device"), m.get("peer_name"), float(r["value"][1])))
    except Exception as e:                                    # noqa: BLE001
        print("     ", e)

    print("\n   probe coverage by service (a Probe CRD reporting NO series = silent blind spot):")
    try:
        rs = q("/api/v1/query", query="count by (service) (probe_success)"
               ).get("data", {}).get("result", [])
        reporting = {r["metric"].get("service") for r in rs}
        for r in rs:
            print("     %-38s %s targets" % (r["metric"].get("service"), r["value"][1]))
        crds = subprocess.run(["kubectl", "get", "probes.monitoring.coreos.com", "-A", "-o",
                               "jsonpath={range .items[*]}{.metadata.labels.service}{'\\n'}{end}"],
                              capture_output=True, text=True).stdout.split()
        named = {c for c in crds if c and c != "<no"}
        print("     Probe CRDs whose service label reports nothing:",
              sorted(named - reporting) or "none")
    except Exception as e:                                    # noqa: BLE001
        print("     ", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
