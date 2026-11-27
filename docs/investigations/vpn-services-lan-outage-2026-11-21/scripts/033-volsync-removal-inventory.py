#!/usr/bin/env python3
"""Step 033 - Volsync removal inventory (READ-ONLY).

The user confirmed volsync is retired and asked for it removed. Before deleting anything this
answers the four questions that could turn a cleanup into an outage:

  1. Is any app still ACTIVELY including a volsync component (vs a commented-out line)?
     Deleting the component dir would then break that app's Flux build.
  2. What is still running in-cluster (operator, namespace, CRs, CRDs) and who owns it - because
     removing Git config does not remove live state, and prune behaviour differs per Kustomization.
  3. Does snapshot-controller (needed by kopiur's local snapshots) come from the same directory?
  4. Which secrets/OCI/NetworkPolicy/doc references name volsync, so nothing is left dangling.
"""
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).rsplit("/docs", 1)[0]


def sh(*args, **kw):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True, **kw)


def kubectl(*args):
    """kubectl without failing the whole inventory on a missing resource."""
    r = sh("kubectl", *args)
    return (r.stdout or "").strip() if r.returncode == 0 else "ERROR: " + (r.stderr or "").strip().splitlines()[0][:90]


def section(title):
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def main():
    section("1. EVERY file mentioning volsync, classified")
    tracked = sh("git", "grep", "-l", "-i", "volsync").stdout.split()
    active, commented, other = [], [], []
    for f in tracked:
        try:
            txt = open(os.path.join(REPO, f)).read()
        except OSError:
            continue
        hits = [ln for ln in txt.splitlines() if "volsync" in ln.lower()]
        # an active component/resource include is a list item that is not commented
        act = [h for h in hits
               if re.match(r"\s*-\s+\S*volsync\S*", h) and not h.strip().startswith("#")]
        if act:
            active.append((f, act))
        elif all(h.strip().startswith("#") for h in hits):
            commented.append((f, len(hits)))
        else:
            other.append((f, [h.strip()[:96] for h in hits if not h.strip().startswith("#")]))
    print("  ACTIVE include lines (would break if the component is deleted): %d files" % len(active))
    for f, lines in active:
        print("     %s" % f)
        for l in lines:
            print("        %s" % l.strip()[:100])
    print("  non-comment, non-list references: %d files" % len(other))
    for f, lines in other[:40]:
        print("     %-72s %s" % (f.replace("kubernetes/", ""), " | ".join(lines)[:60]))
    print("  commented-only references: %d files (%d lines total)"
          % (len(commented), sum(n for _, n in commented)))

    section("2. Files/dirs that exist to run volsync (removal candidates)")
    for p in ["kubernetes/apps/volsync-system", "kubernetes/components/volsync",
              "kubernetes/components/volsync-no-r2", "kubernetes/components/volsync-only-r2"]:
        r = os.path.join(REPO, p)
        if os.path.isdir(r):
            files = []
            for root, _, names in os.walk(r):
                for n in names:
                    files.append(os.path.relpath(os.path.join(root, n), REPO))
            print("  %s  (%d files)" % (p, len(files)))
            for f in sorted(files):
                print("      ", f)
        else:
            print("  %s  (absent)" % p)

    section("3. Is snapshot-controller (kopiur dependency) defined in the volsync tree?")
    hits = sh("git", "grep", "-l", "-i", "snapshot-controller").stdout.split()
    for f in hits:
        print("  ", f)
    print("\n  live snapshot-controller and its owner:")
    out = kubectl("-n", "kube-system", "get", "deploy", "snapshot-controller",
                  "-o", "jsonpath={.metadata.labels} ||| {.metadata.annotations}")
    print("   ", (out or "none")[:600])

    section("4. Live cluster state that Git removal will NOT delete")
    print("  namespace volsync-system:")
    print("   ", kubectl("get", "ns", "volsync-system", "--no-headers") or "-")
    print("  workloads in volsync-system:")
    print("   ", (kubectl("get", "deploy,sts,ds -n volsync-system", "--no-headers") or "  none").replace("\n", "\n    "))
    print("  volsync CRD instances (any namespace):")
    for crd in ["replicationsources.volsync.backube", "replicationdestinations.volsync.backube",
                "kopiamaintenances.volsync.backube"]:
        print("     %-42s %s" % (crd, (kubectl("get", crd, "-A", "--no-headers") or "none").splitlines()[0][:110]))
    print("  volsync CRDs present (deleting these is a separate, mutating decision):")
    crds = [l for l in kubectl("get", "crd", "--no-headers").splitlines() if "volsync" in l]
    print("    ", "\n     ".join(crds) if crds else "none")
    print("  Flux Kustomizations naming volsync:")
    print("   ", (kubectl("get", "kustomizations", "-A", "--no-headers") or "none").replace("\n", "\n    "))

    section("5. Secrets / SOPS rules / docs naming volsync")
    for pat in ["volsync", "VOLSYNC"]:
        out = sh("git", "grep", "-l", pat, "--", "*.sops.yaml", ".sops.yaml", "docs", ".github",
                 "Taskfile.yaml", ".task").stdout.split()
        for f in sorted(set(out)):
            print("  [%s] %s" % (pat, f))
    print("\n  r2/s3 secret refs still used by kopiur (must NOT be removed):")
    out = sh("git", "grep", "-l", "-i", "kopiur", "--", "*.yaml").stdout.split()
    print("     %d kopiur files" % len(out))
    for f in out:
        if "secret" in f.lower():
            print("       ", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
