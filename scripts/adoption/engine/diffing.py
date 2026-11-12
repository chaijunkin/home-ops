#!/usr/bin/env python3
"""Plan comparison keyed by JSON Pointer with name selectors.

Raw array indices are a terrible review surface: insert one output and every later
element reports as replaced, which burrows the single real change under noise. So
an array whose elements all carry `name`, `id`, or `unit` is addressed by that
value (`/outputs/@name=hermes-agent/slots`) and only positional arrays fall back
to an index.

Digest fields are volatile by nature — they change when anything changes — so they
are excluded unless a caller explicitly asks for them.
"""

from __future__ import annotations

SELECTOR_KEYS = ("name", "id", "unit", "key")
VOLATILE = ("planDigest", "desiredStateDigest")


def pointers(value, prefix: str = "") -> dict[str, object]:
    """Flatten to {pointer: leaf-value}. Containers have no leaf of their own."""
    if isinstance(value, dict):
        if not value:
            return {prefix or "/": {}}
        out: dict[str, object] = {}
        for key in sorted(value):
            out.update(pointers(value[key], f"{prefix}/{_escape(key)}"))
        return out
    if isinstance(value, list):
        if not value:
            return {prefix or "/": []}
        selector = _selector(value)
        out = {}
        for index, item in enumerate(value):
            if selector is None:
                out.update(pointers(item, f"{prefix}/{index}"))
            else:
                key = str(item[selector])
                out.update(pointers(item, f"{prefix}/@{selector}={_escape(key)}"))
        return out
    return {prefix or "/": value}


def diff(before: dict, after: dict, *, include_volatile: bool = False) -> dict:
    """Structural difference between two records, safe to quote in a PR."""
    old, new = pointers(before), pointers(after)
    if not include_volatile:
        old = {k: v for k, v in old.items() if not _volatile(k)}
        new = {k: v for k, v in new.items() if not _volatile(k)}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    shared = set(old) & set(new)
    changed = sorted(
        (
            {"pointer": key, "before": old[key], "after": new[key]}
            for key in shared
            if old[key] != new[key]
        ),
        key=lambda item: item["pointer"],
    )
    return {
        "identical": not (added or removed or changed),
        "added": [{"pointer": p, "value": new[p]} for p in added],
        "removed": [{"pointer": p, "value": old[p]} for p in removed],
        "changed": changed,
    }


def _selector(items: list) -> str | None:
    if not all(isinstance(item, dict) for item in items):
        return None
    for key in SELECTOR_KEYS:
        values = [item.get(key) for item in items]
        if all(isinstance(v, str) and v for v in values) and len(set(values)) == len(values):
            return key
    return None


def _volatile(pointer: str) -> bool:
    return any(marker in pointer for marker in VOLATILE)


def _escape(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")
