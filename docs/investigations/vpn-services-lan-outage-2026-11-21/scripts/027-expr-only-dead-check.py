#!/usr/bin/env python3
"""Step 027 - Dead-metric check restricted to expr: values only.

READ-ONLY.

Step 026 scanned whole files, so prose in comments/annotations ("WAN_PPPOE", "runbook_url",
"exception_class") looked like metrics. Here only the actual PromQL of each alert is parsed, and
each surviving unknown metric is re-checked with an instant query plus a 30 d series query so a
name that exists but is currently idle is not called dead.
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

STOP = set("""
avg avg_over_time count count_over_time sum max min rate irate increase resets absent
absent_over_time time vector scalar label_replace label_join histogram_quantile histogram_count
histogram_sum quantile topk bottomk offset bool clamp_max clamp_min ceil floor round abs delta
idelta deriv predict_linear sort sort_desc sgn present_over_time by without on ignoring
group_left group_right and or unless
""".split())
METRIC = re.compile(r"(?<![A-Za-z0-9_:])([a-zA-Z_][a-zA-Z0-9_]{4,})(?![A-Za-z0-9_(])")


def q(path, **params):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r)


def exprs(path):
    """Yield (alertname, promql) for every alert in a PrometheusRule yaml."""
    out, alert, buf, indent = [], None, [], 0
    for raw in open(path):
        line = raw.rstrip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = re.match(r"^(\s*)-\s*alert:\s*(\S+)", line)
        if m:
            alert, buf, indent = m.group(2), [], 0
            continue
        m = re.match(r"^(\s*)expr:\s*(.*)$", line)
        if m and alert:
            buf = [m.group(2)] if m.group(2) and m.group(2) not in (">", "|", ">-", "|-") else []
            indent = len(m.group(1))
            continue
        if buf is not None and alert:
            cur = len(line) - len(line.lstrip())
            if cur > indent:
                buf.append(line.strip())
            else:
                out.append((alert, " ".join(buf)))
                alert, buf = None, None
    if alert and buf:
        out.append((alert, " ".join(buf)))
    return [(a, e) for a, e in out if e]


def main():
    now = int(time.time())
    live = set(q("/api/v1/label/__name__/values").get("data", []))
    groups = q("/api/v1/rules").get("data", {}).get("groups", [])
    deployed = {}
    for g in groups:
        for r in g.get("rules", []):
            if r.get("type") == "alerting":
                deployed[r["name"]] = " ".join((r.get("query") or "").split())

    files = [f for f in subprocess.run(["git", "ls-files", "*prometheusrule*.yaml"],
                                       cwd=REPO, capture_output=True, text=True).stdout.split()]
    print("%-4s %-46s %-34s %s" % ("flag", "alert", "file", "missing metric"))
    print("-" * 128)
    real = []
    seen_dead = set()
    for f in files:
        path = os.path.join(REPO, f)
        for alert, expr in exprs(path):
            if alert not in deployed:
                continue                      # not loaded -> obsolete config, handled separately
            cands = {m for m in METRIC.findall(re.sub(r'"(?:[^"\\]|\\.)*"', " ", expr))
                     if m not in STOP and "_" in m}
            missing = []
            for m in sorted(cands):
                if m in live:
                    continue
                # second opinion: 30 d of series for the name, in case it is idle not absent
                try:
                    res = q("/api/v1/query_range", query="count(%s)" % m,
                            start=str(now - 30 * 86400), end=str(now), step="1d")
                    if res.get("data", {}).get("result"):
                        missing.append(m + " (idle 30d)")
                except Exception:             # noqa: BLE001
                    pass
            dead = [m for m in sorted(cands) if m not in live]
            dead = [m for m in dead if m + " (idle 30d)" not in missing]
            for m in dead:
                real.append((alert, f, m))
                print("%-4s %-46s %-34s %s" % ("DEAD", alert, os.path.basename(os.path.dirname(f))
                                               + "/" + os.path.basename(f), m))
                seen_dead.add(alert)
    print("\nalerts loaded but permanently unable to fire: %d" % len(seen_dead))
    for a in sorted(seen_dead):
        print("   ", a)

    print("\n===== deployed expression for each (what Prometheus is actually running) =====")
    for a in sorted(seen_dead):
        print("\n--- %s" % a)
        print("    " + deployed[a][:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
