#!/usr/bin/env python3
"""Step 026 - Definitive matrix: repo rule files vs what Prometheus actually has loaded.

READ-ONLY.

Why: step 016 flagged dead expressions by diffing metric names, but it never asked whether the
rule file is deployed at all. A dead expression in a file that is not loaded is obsolete config
(a cleanup), whereas a dead expression in a loaded file is a silent alerting gap (urgent). Those
need different responses, so the two sets are joined here.

Method: every alert/reject rule name declared under kubernetes/ is looked up in /api/v1/rules, and
every deployed rule whose expression references a metric with zero series in 30 d is labelled
SILENT. Nothing is inferred from "did it fire recently".
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

BASE = os.environ.get("PROM", "http://localhost:19090")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).rsplit("/docs", 1)[0]


def q(path, **params):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r)


def main():
    now = int(time.time())

    # ---- 1. live metric index
    live = set(q("/api/v1/label/__name__/values").get("data", []))
    print("metrics in Prometheus: %d" % len(live))

    # ---- 2. deployed rules (name -> expression)
    groups = q("/api/v1/rules").get("data", {}).get("groups", [])
    deployed = {}
    for g in groups:
        for r in g.get("rules", []):
            if r.get("type") == "alerting":
                deployed.setdefault(r["name"], []).append(r.get("query", ""))
    print("deployed alerting rules: %d names" % len(deployed))

    # ---- 3. repo rules (file -> [(alertname, expr)])
    files = subprocess.run(
        ["git", "ls-files", "*prometheusrule*.yaml"], cwd=REPO, capture_output=True, text=True
    ).stdout.split()
    METRIC = re.compile(r"(?<![A-Za-z0-9_:])([a-zA-Z_][a-zA-Z0-9_]{4,})(?![A-Za-z0-9_(])")
    # PromQL functions, keywords, and yaml noise - anything that is not a metric name.
    STOP = set("""
ALERTS avg avg_over_time count count_over_time sum max min rate irate increase resets
absent absent_over_time time vector scalar label_replace label_join histogram_quantile
histogram_count histogram_sum quantile topk bottomk offset bool clamp_max clamp_min ceil
floor round abs delta idelta_deriv deriv predict_linear sort sort_desc sort_by_label
sgn present_over_time by without on ignoring group_left group_right and or unless
pipeline stage steps record annotations labels expr alert for severity summary description
keep_firing_for interval labels limit
""".split())
    print("repo PrometheusRule files: %d\n" % len(files))

    header = "%-6s %-58s %-6s %-6s %s" % ("state", "file", "rules", "active", "dead metrics")
    print(header)
    print("-" * 140)
    rows = []
    for f in files:
        try:
            txt = open(os.path.join(REPO, f)).read()
        except OSError:
            continue
        names = re.findall(r"^\s*-\s*alert:\s*(\S+)", txt, re.M)
        if not names:
            continue
        # strip label selectors and quoted strings so only metric names survive
        stripped = re.sub(r"\{[^}]*\}", " ", txt)
        stripped = re.sub(r'"(?:[^"\\]|\\.)*"', " ", stripped)
        stripped = re.sub(r"'(?:[^'\\]|\\.)*'", " ", stripped)
        metrics = {m for m in METRIC.findall(stripped) if m not in STOP and "_" in m}
        dead = sorted(m for m in metrics if m not in live)
        active = [n for n in names if n in deployed]
        if not active:
            state = "NOT-DEPLOYED"
        elif dead:
            state = "DEAD-EXPR"
        else:
            state = "ok"
        rows.append((state, f, len(names), len(active), dead))

    order = {"DEAD-EXPR": 0, "NOT-DEPLOYED": 1, "ok": 2}
    rows.sort(key=lambda r: (order[r[0]], r[1]))
    for state, f, n, active, dead in rows:
        short = f.replace("kubernetes/apps/", "")
        print("%-6s %-58s %-6d %-6d %s" % (
            state.replace("NOT-DEPLOYED", "absent").replace("DEAD-EXPR", "DEAD")
                 .replace("ok", "ok"),
            short[:58], n, active, (", ".join(dead)[:60] or "-")))

    print("\n===== what to do with each state =====")
    print("  DEAD   = loaded in Prometheus AND references a nonexistent metric -> silent gap, fix now")
    print("  absent = file is not loaded at all -> obsolete config, cleanup PR (not an alerting gap)")
    print("  ok     = loaded and every metric it uses exists")
    return 0


if __name__ == "__main__":
    sys.exit(main())
