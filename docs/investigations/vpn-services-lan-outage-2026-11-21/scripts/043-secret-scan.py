#!/usr/bin/env python3
"""Step 043 - Secret scan of the investigation tree before it goes to a PUBLIC repo (READ-ONLY).

The repo is github.com/chaijunkin/home-ops, visibility=PUBLIC. Results files from a firewall debug
session are exactly where a WireGuard private key, an API secret, or a Kopia repository password ends
up, because the natural thing to paste is `config.xml` and the natural thing to dump is a full CR.

Scans two sets separately:
  NEW     uncommitted files about to be pushed
  PUBLIC  already-committed files under the same folder (a hit here is a live leak, not a future one)

Deliberately does NOT flag RFC1918 addresses, hostnames, or interface names: this repo has always
carried internal topology and flagging it would bury a real key.
"""

import base64
import binascii
import os
import re
import subprocess
import sys

ROOT = "docs/investigations/vpn-services-lan-outage-2026-11-21"

PATTERNS = [
    ("PEM private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("PEM anything", re.compile(r"-----BEGIN [A-Z ]{3,30}-----")),
    ("WG private_key= assignment", re.compile(r"(?i)private[_-]?key['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9+/]{40,}")),
    ("WG preshared key", re.compile(r"(?i)preshared[_-]?key['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9+/=]{40,}")),
    ("base64 32-byte blob labelled secret", re.compile(r"(?i)(secret|token|passwd|password|apikey|api_key)['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9+/_-]{16,}")),
    ("GitHub token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|github_pat_[A-Za-z0-9_]{20,}")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Cloudflare/API bearer", re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}")),
    ("Kopia repo password line", re.compile(r"(?i)(repository password|repo password|password:)\s*\S{8,}")),
    ("URL with embedded credentials", re.compile(r"\b(?:https?|sftp|postgres(?:ql)?|mysql|redis)://[^/\s:]+:[^@\s]{4,}@\S+")),
    ("OCID", re.compile(r"\bocid1\.[a-z]+\.[a-z]{2,}\.aa[A-Za-z0-9+/=]{12,}")),
    ("SOPS plaintext marker", re.compile(r"sops:\s*ENC\[|UNSAFE-|REDACT-ME")),
]

# Bare base64 that decodes to exactly 32 bytes is the WireGuard key shape. Reported separately and
# only with context, because `kubectl -o wide` output and image digests produce lookalikes.
BARE_B64 = re.compile(r"\b[A-Za-z0-9+/]{43}=\b")
ALLOW_WORDS = ("sha256", "digest", "@sha256", "uid", "resourceVersion", "imageID", "signature")


def scan(path, label, findings):
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        print(f"  !! unreadable {path}: {exc}")
        return
    for lineno, line in enumerate(text.splitlines(), 1):
        # Skip this script's own pattern definitions: they are regex sources, not content, and they
        # otherwise match themselves forever (three permanent false positives).
        if re.match(r'^\s*\("[^"]+",\s*re\.compile', line):
            continue
        for name, pat in PATTERNS:
            for m in pat.finditer(line):
                raw = m.group(0).strip()
                tail = raw.split("=", 1)[-1].strip("\"'")
                if (path, name, raw) in REVIEWED or (path, name, tail) in REVIEWED:
                    ALLOWED.append((label, path, lineno, name, tail))
                    continue
                findings.append((label, path, lineno, name, redact(raw)))
        for m in BARE_B64.finditer(line):
            low = line.lower()
            if any(w in low for w in ALLOW_WORDS):
                continue
            try:
                raw = base64.b64decode(m.group(0), validate=True)
            except (binascii.Error, ValueError):
                continue
            if len(raw) == 32:
                printable = sum(1 for b in raw if 32 <= b < 127)
                if printable < 20:  # high-entropy => key material, not an id
                    findings.append((label, path, lineno,
                                     "32-byte high-entropy base64 (WG key shape)",
                                     redact(m.group(0))))


def redact(s):
    s = s.strip()
    return s[:10] + "…" + f"<{len(s)} chars>" if len(s) > 18 else s


# Reviewed-and-benign hits, matched on the literal value rather than a line number, so the gate stays
# silent for these but re-arms the moment the value changes. 008 line 24 is `SECRET=` holding a
# Kubernetes Secret NAME used as `secretRef: {name: $SECRET}`; the real OPNsense key material is 80
# chars and comes from Bitwarden via ExternalSecret (hash-compared 2026-11-27, no match).
REVIEWED = [
    ("docs/investigations/vpn-services-lan-outage-2026-11-21/scripts/008-opnsense-api-triage.sh",
     "base64 32-byte blob labelled secret", "opnsense-exporter-secret"),
]
ALLOWED = []


def redact(s):
    s = s.strip()
    return s[:10] + "…" + f"<{len(s)} chars>" if len(s) > 18 else s


def tracked_state():
    out = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout
    new, modified = [], []
    for ln in out.splitlines():
        code, path = ln[:2], ln[3:].strip()
        if not path.startswith(ROOT):
            continue
        if code == "??":
            # git collapses clean untracked directories to one entry; expand so nothing is skipped,
            # and drop anything git itself would ignore (e.g. __pycache__ from a local run).
            if os.path.isdir(path):
                for base, _dirs, files in os.walk(path):
                    for f in files:
                        full = os.path.join(base, f)
                        if subprocess.run(["git", "check-ignore", "-q", full],
                                          capture_output=True).returncode != 0:
                            new.append(full)
            elif subprocess.run(["git", "check-ignore", "-q", path], capture_output=True).returncode != 0:
                new.append(path)
        else:
            modified.append(path)
    return new, modified


def main():
    new, modified = tracked_state()
    committed = subprocess.run(["git", "ls-files", ROOT], capture_output=True, text=True).stdout.split()
    public = [p for p in committed if os.path.exists(p)]

    print(f"repo root files under {ROOT}: {len(new) + len(modified) + len(public)} total")
    print(f"  untracked (new):      {len(new)}")
    print(f"  modified committed:   {len(modified)}")
    print(f"  committed untouched:  {len(public)}\n")

    findings = []
    for p in sorted(set(new)):
        scan(p, "NEW", findings)
    for p in sorted(set(modified)):
        scan(p, "NEW", findings)      # the diff being pushed
    for p in sorted(set(public)):
        scan(p, "PUBLIC", findings)

    if ALLOWED:
        print(f"reviewed benign hits (suppressed, value-matched): {len(ALLOWED)}")
        for label, path, lineno, name, val in ALLOWED:
            print(f"   {name:44s} {path}:{lineno}  {val}")
        print()

    if not findings:
        print("RESULT: PASS - no secret-shaped content in either set.")
        return 0

    for label in ("PUBLIC", "NEW"):
        hits = [f for f in findings if f[0] == label]
        if not hits:
            continue
        print(f"{'!!' if label == 'PUBLIC' else '!!'} {label}: {len(hits)} hit(s)")
        for _, path, lineno, name, val in hits[:60]:
            print(f"   {name:44s} {path}:{lineno}  {val}")
        if len(hits) > 60:
            print(f"   ... {len(hits) - 60} more")
        print()
    print("RESULT: REVIEW REQUIRED before pushing.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
