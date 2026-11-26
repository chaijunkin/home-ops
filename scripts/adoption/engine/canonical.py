#!/usr/bin/env python3
"""Canonical JSON and domain-separated digest identity.

Two rules carry all the weight:

1. A record's bytes depend only on meaning. Keys are sorted, insignificant
   whitespace is gone, and every collection that has no ordering meaning is
   sorted explicitly by the producer. The same checkout must compile the same
   Plan bytes, or "did this change?" has no answer.

2. Digests are domain separated: sha256(UTF8(kind) || 0x00 || canonical-json).
   A kind tag is frozen per object family, so a Definition can never collide with
   a Plan that happens to serialise to the same bytes, and a digest quoted in a
   transcript says which kind of thing it names.
"""

from __future__ import annotations

import hashlib
import json

KIND_DEFINITION = "adoption.definition/v1"
KIND_ENVIRONMENT = "adoption.environment/v1"
KIND_REGISTRY = "adoption.registry/v1"
KIND_LOCK = "adoption.lock/v1"
KIND_PLAN = "adoption.plan/v1"
KIND_CLOSURE = "adoption.closure/v1"
KIND_POLICY = "adoption.policy/v1"


def canonical_json(obj) -> bytes:
    """Deterministic UTF-8 bytes for a JSON-compatible value."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def pretty(obj) -> str:
    """Display-only. Never a canonical input and never digested."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)


def digest(kind_tag: str, obj) -> str:
    if not kind_tag or "\x00" in kind_tag:
        raise ValueError("kind tag must be non-empty and NUL-free")
    h = hashlib.sha256()
    h.update(kind_tag.encode("utf-8"))
    h.update(b"\x00")
    h.update(canonical_json(obj))
    return f"sha256:{h.hexdigest()}"


def sortable(*keys) -> callable:
    """A stable sort key for records held in lists that must serialise deterministically."""
    return lambda item: tuple(str(item.get(k, "")) for k in keys)
