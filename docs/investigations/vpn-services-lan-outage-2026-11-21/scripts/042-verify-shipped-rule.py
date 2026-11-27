#!/usr/bin/env python3
"""Step 042 - Verify the shipped SpeedtestExporterAbsent expression verbatim (READ-ONLY).

Extracts the expr block straight out of the YAML by indentation (no YAML parser needed, so what is
tested is byte-identical to what is committed) and evaluates it against the live Prometheus:

  1. healthy cluster            -> must be EMPTY
  2. same text, job that has no samples -> must be 1  (proves the "target gone" arm)
  3. every other rule in the file       -> must parse, i.e. no collateral damage

Usage: python3 042-verify-shipped-rule.py [path/to/prometheusrule.yaml]
Requires: kubectl -n observability port-forward svc/prometheus-operated 9091:9090
"""

import json
import re
import sys
import urllib.parse
import urllib.request

BASE = "http://localhost:9091"
PATH = sys.argv[1] if len(sys.argv) > 1 else (
    "kubernetes/apps/observability/exporters/speedtest-exporter/app/prometheusrule.yaml"
)


def q(expr):
    url = BASE + "/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    with urllib.request.urlopen(url, timeout=60) as r:
        body = json.load(r)
    if body.get("status") != "success":
        raise RuntimeError(body.get("error", "unknown promql error"))
    return body["data"]["result"]


def parse_rules(path):
    """Minimal PrometheusRule reader: returns [(alert, expr, for)] in file order."""
    out, cur, buf, indent, in_expr, block_for = [], None, [], 0, False, None
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        m = re.match(r"^(\s*)- alert:\s*(\S+)\s*$", line)
        if m:
            if cur:
                out.append((cur, "\n".join(buf).strip(), block_for))
            cur, buf, block_for = m.group(2), [], None
            continue
        if cur is None:
            continue
        if re.match(r"^\s*expr:\s*\|\s*$", line):
            indent = len(line) - len(line.lstrip())
            in_expr = True
            continue
        if in_expr:
            if line.strip() and (len(line) - len(line.lstrip())) > indent:
                buf.append(line.strip())
            else:
                in_expr = False
        mf = re.match(r"^\s*for:\s*(\S+)\s*$", line)
        if mf:
            block_for = mf.group(1)
    if cur:
        out.append((cur, "\n".join(buf).strip(), block_for))
    return out


rules = parse_rules(PATH)
print(f"parsed {len(rules)} rules from {PATH}\n")

target = next((r for r in rules if r[0] == "SpeedtestExporterAbsent"), None)
if not target:
    print("FAIL: SpeedtestExporterAbsent not found in file")
    raise SystemExit(1)

name, expr, for_val = target
print(f"{name}   for: {for_val}")
print("  expression under test (verbatim from the file):")
for ln in expr.splitlines():
    print(f"    {ln}")

ok = True
res = q(expr)
if res:
    ok = False
    print(f"\n  FAIL healthy cluster -> {[r['value'][1] for r in res]} (would fire right now)")
else:
    print("\n  PASS healthy cluster -> EMPTY")

gone = expr.replace("speedtest-exporter", "speedtest-exporter-gone-simulated")
res = q(gone)
vals = [r["value"][1] for r in res]
if vals != ["1"]:
    ok = False
    print(f"  FAIL target-gone arm -> {vals} (expected ['1'])")
else:
    print(f"  PASS target-gone arm -> {vals}")

# arm2 must not need arm1: a target whose scrapes all fail still produces samples. Simulated by
# asking for any job in the cluster that is currently 0 over 130m - if none, the arm is simply inert.
res = q('max_over_time(up[130m]) == 0')
print(f"  info max_over_time(up[130m]) == 0 across all jobs -> {len(res)} job(s) currently 0 "
      f"(these are genuinely failing scrapes, arm2 is meant to catch them)")
for r in res[:6]:
    print(f"       {json.dumps({k: v for k, v in r['metric'].items() if k in ('job', 'instance')})}")

print("\nrest of the file:")
for other, oexpr, ofor in rules:
    if other == name:
        continue
    try:
        r = q(oexpr)
        state = "not firing" if not r else "firing: " + ", ".join(
            f"{x['value'][1]}@{json.dumps({k: v for k, v in x['metric'].items() if k in ('instance', 'job')})[:60]}"
            for x in r[:3]
        )
        print(f"  {other:34s} for={str(ofor):5s} -> {state}")
    except Exception as exc:                                # noqa: BLE001
        ok = False
        print(f"  {other:34s} -> PROMQL ERROR {exc}")

print("\nRESULT:", "PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
