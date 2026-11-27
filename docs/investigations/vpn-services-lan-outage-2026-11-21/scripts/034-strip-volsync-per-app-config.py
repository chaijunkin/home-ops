#!/usr/bin/env python3
"""Step 034 - Strip per-app volsync config (mechanical, guarded).

Three classes of dead reference are removed from kubernetes/apps:

  A. commented component includes  ->  "# - ../../../../components/volsync[-no-r2|-only-r2]"
  B. substitution values           ->  "VOLSYNC_CAPACITY: 5Gi" / "VOLSYNC_CLAIM: foo"
  C. namespace annotations         ->  "volsync.backube/privileged-movers: \"true\""

Deleting a line can leave its parent key with no value (YAML null), which Flux/kubeconform
rejects for typed keys like spec.components ([]string) and spec.postBuild.substitute. So after
each file is edited, prune_empty_keys() drops any "key:" line whose body vanished - iterating so
that removing an empty "substitute:" also removes a now-empty "postBuild:".

Comment lines are indentation-insignificant in YAML, so leftover sibling comments stay valid when
their parent key is dropped.

Run without --apply to see what would change.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))          # <repo>/docs/investigations/<topic>/scripts
REPO = HERE.split("/docs/investigations/")[0]              # <repo>
APPS = os.path.join(REPO, "kubernetes", "apps")

PAT_INCLUDE = re.compile(r"^\s*(?:#\s*)+-\s+\.\./.*components/volsync(?:-no-r2|-only-r2)?\s*$")
PAT_VAR = re.compile(r"^\s*#?\s*VOLSYNC_[A-Z_]+:\s*\S.*$")
PAT_MOVERS = re.compile(r"volsync\.backube/privileged-movers\s*:")
# a mapping key with no inline value: "  components:"  (optionally trailing comment)
PAT_KEY = re.compile(r"^\s*-?\s*[^:#][^:]*:\s*(#.*)?$")


def indent_of(line):
    return len(line) - len(line.lstrip())


def prune_empty_keys(lines):
    """Drop 'key:' lines whose body disappeared. Returns (lines, dropped)."""
    dropped = []
    for _ in range(6):  # bounded: nesting depth of spec.postBuild.substitute is 3
        emptied = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or not PAT_KEY.match(line):
                continue
            ind = indent_of(line)
            body = None
            for nxt in lines[i + 1:]:
                s = nxt.strip()
                if not s or s.startswith("#"):
                    continue
                body = nxt
                break
            # a document separator or a sibling/less-indented key means no body
            if body is None or body.strip() == "---" or indent_of(body) <= ind:
                emptied = (i, stripped)
                break
        if not emptied:
            break
        i, name = emptied
        dropped.append(name)
        lines = lines[:i] + lines[i + 1:]
    return lines, dropped


def main():
    apply = "--apply" in sys.argv
    touched, total = 0, {"include": 0, "var": 0, "movers": 0, "empty-key": 0}

    for root, _, names in os.walk(APPS):
        for name in sorted(names):
            if not name.endswith(".yaml"):
                continue
            path = os.path.join(root, name)
            with open(path) as fh:
                original = fh.read()
            lines = original.split("\n")
            kept, counts = [], {"include": 0, "var": 0, "movers": 0}
            for line in lines:
                if PAT_INCLUDE.match(line):
                    counts["include"] += 1
                    continue
                if PAT_VAR.match(line):
                    counts["var"] += 1
                    continue
                if PAT_MOVERS.search(line):
                    counts["movers"] += 1
                    continue
                kept.append(line)
            if not any(counts.values()):
                continue
            kept, dropped_keys = prune_empty_keys(kept)
            rel = os.path.relpath(path, REPO)
            bits = [f"{k}={v}" for k, v in counts.items() if v]
            if dropped_keys:
                bits.append("also-dropped:" + ",".join(dropped_keys))
            print(f"  {rel:60s} {', '.join(bits)}")
            touched += 1
            for k in counts:
                total[k] += counts[k]
            total["empty-key"] += len(dropped_keys)
            if apply:
                with open(path, "w") as fh:
                    fh.write("\n".join(kept))

    print("\n  mode: %s" % ("APPLIED" if apply else "dry-run"))
    print("  files: %d | includes: %d | VOLSYNC_* vars: %d | privileged-movers: %d | empty keys dropped: %d"
          % (touched, total["include"], total["var"], total["movers"], total["empty-key"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
