#!/usr/bin/env python3
"""YAML reading, delegated to `yq` (mikefarah v4).

Python's stdlib has no YAML parser and the estate's manifests need real YAML
semantics — multi-document files, block scalars, anchors, nested Helm values.
Everything after parsing is stdlib, and a missing `yq` is an environment error
that stops the run rather than a skipped check.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from errors import E_TOOL_MISSING, fail

_YQ: str | None = None


def yq() -> str:
    global _YQ
    if _YQ is None:
        _YQ = shutil.which("yq")
        if not _YQ:
            fail(E_TOOL_MISSING, "yq (mikefarah v4) is not on PATH", hint="mise install")
    return _YQ


def run_yq(expression: str, *files: str, cwd: str | None = None) -> str:
    if not files:
        return ""
    proc = subprocess.run(
        [yq(), "-o=json", "-I=0", expression, *files],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        fail(
            E_TOOL_MISSING,
            f"yq exited {proc.returncode}: {proc.stderr.strip()[:400]}",
            hint=f"expression {expression!r} over {len(files)} file(s)",
        )
    return proc.stdout


def decode_stream(out: str):
    """Yield each JSON value in `out`, which may be concatenated without separators."""
    decoder = json.JSONDecoder()
    idx, n = 0, len(out)
    while idx < n:
        while idx < n and out[idx] in " \n\r\t":
            idx += 1
        if idx >= n:
            return
        value, end = decoder.raw_decode(out, idx)
        idx = end
        yield value


def read_yaml(path: str, cwd: str | None = None):
    """One document from one file. Multi-document inputs are rejected here."""
    out = run_yq(".", path, cwd=cwd)
    docs = list(decode_stream(out))
    if len(docs) > 1:
        fail(E_TOOL_MISSING, f"{path}: expected one document, found {len(docs)}")
    return docs[0] if docs else None
