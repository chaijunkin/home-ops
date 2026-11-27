#!/usr/bin/env python3
"""Step 025 - Rule health + backup-coverage check via the Prometheus rules API.

READ-ONLY.

Why this instead of trusting step 023: a rule whose metric is simply *absent* still evaluates
"successfully" to an empty result, so the rules API will call it healthy. Conversely the API finds
rules that are outright ERRORING (bad expression, template error) which a metric-name diff cannot
see. The two audits are complementary and both are needed.

Also answers the backup question raised by volsync being retired: does the replacement (kopiur)
actually have alert rules loaded, and are they healthy?
"""
import json
import os
import sys
import urllib.parse
import urllib.request

BASE = os.environ.get("PROM", "http://localhost:19090")


def q(path, **params):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=90) as r:
        return json.load(r)


def main():
    d = q("/api/v1/rules")
    groups = d.get("data", {}).get("groups", [])
    rules = [r for g in groups for r in g.get("rules", [])]
    alerts = [r for r in rules if r.get("type") == "alerting"]
    recs = [r for r in rules if r.get("type") == "recording"]

    print("groups=%d  rules=%d (alerting=%d, recording=%d)"
          % (len(groups), len(rules), len(alerts), len(recs)))

    health = {}
    for r in rules:
        health[r.get("health")] = health.get(r.get("health"), 0) + 1
    print("health:", health)

    print("\n===== A. Rules that are ERRORING or never evaluated =====")
    bad = [r for r in rules if r.get("health") != "ok"]
    if not bad:
        print("   none - every loaded rule evaluates cleanly")
    for r in bad[:40]:
        print("   %-14s %-40s %s" % (r.get("health"), r.get("name"),
                                     (r.get("lastError") or "")[:110]))

    print("\n===== B. Rules that are loaded but produce NOTHING, ever =====")
    print("   (queried over the last 30 d; a rule here can be 'healthy' and still be blind)")
    empty = []
    for r in alerts:
        name = r.get("name")
        try:
            res = q("/api/v1/query_range", query='ALERTS{alertname="%s"}' % name,
                    start=str(int(os.environ.get("T0", 0))), end=str(int(os.environ.get("T1", 0))),
                    step="6h").get("data", {}).get("result", [])
        except Exception:                                     # noqa: BLE001
            res = []
        states = {tuple(sorted(v[1] for v in s["values"])) for s in res}
        fired = any("firing" in " ".join(st) for st in states)
        pending = any("pending" in " ".join(st) for st in states)
        if not res:
            empty.append((name, "never pending/firing in 30 d"))
        elif not fired:
            empty.append((name, "pending only, never fired"))
    if not empty:
        print("   none")
    for name, why in empty:
        print("   %-44s %s" % (name, why))

    print("\n===== C. Backup coverage after volsync (kopiur) =====")
    kop = [r for r in alerts if "kopiur" in r.get("name", "").lower()
           or "backup" in r.get("name", "").lower() or "snapshot" in r.get("name", "").lower()]
    if not kop:
        print("   !! no backup/snapshot alert rules are loaded at all")
    for r in kop:
        print("   %-36s health=%-5s interval=%-6s lastEval=%s" % (
            r.get("name"), r.get("health"), r.get("interval"),
            (r.get("lastEvaluation") or "")[:19]))
        print("        expr: %s" % " ".join((r.get("query") or "").split())[:120])
        for a in (r.get("alerts") or []):
            print("        now: state=%s labels=%s" % (
                a.get("state"), {k: v for k, v in a.get("labels", {}).items()
                                 if k in ("repository", "schedule", "severity")}))

    print("\n===== D. Where do the backup rules live (file/group)? =====")
    for g in groups:
        names = [r.get("name") for r in g.get("rules", [])]
        if any(("kopiur" in (n or "").lower()) or ("backup" in (n or "").lower()) for n in names):
            print("   group=%-44s file=%s" % (g.get("name"), g.get("file") or "(helm/unknown)"))
    return 0


if __name__ == "__main__":
    import time
    os.environ.setdefault("T1", str(int(time.time())))
    os.environ.setdefault("T0", str(int(time.time()) - 30 * 86400))
    sys.exit(main())
