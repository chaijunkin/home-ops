#!/usr/bin/env python3
"""Authored inputs: Definition, Environment, SlotLibrary, Catalog registry and lock.

Authored files declare intent and carry no digests. The lock is the only
generated input, is machine-written, and is replaced under a compare-and-swap
precondition on the exact bytes the caller read — two agents bumping pins at once
must not silently interleave.

References inside a Definition (`environment:`, `catalog.base`) resolve relative
to that Definition's own directory, so a Definition folder can be moved as a unit.
"""

from __future__ import annotations

import os

from canonical import (
    KIND_DEFINITION,
    KIND_ENVIRONMENT,
    KIND_LOCK,
    KIND_REGISTRY,
    digest,
)
from errors import (
    E_INPUT_MISSING,
    E_LOCK_STALE,
    E_REGISTRY_DIGEST,
    E_SCHEMA,
    E_SLOT_UNKNOWN,
    fail,
)
from strict import list_of, map_of, one_of, validate
from yamlio import read_yaml

SLOT_NODES = ("discover", "render", "verify", "diff", "propose", "observe")
LANES = ("static", "proposed")

DEFINITION_SPEC = {
    "apiVersion": "str",
    "kind": one_of("AdoptionDefinition"),
    "metadata": {"name": "str"},
    "?description": "str",
    "catalog": {"base": "str", "?lock": "str"},
    "environment": "str",
    "slots": one_of("library", "inline"),
    "outputs": list_of({"name": "str", "unit": "str", "slots": list_of("str", minimum=1)}, minimum=1),
}

ENVIRONMENT_SPEC = {
    "apiVersion": "str",
    "kind": one_of("AdoptionEnvironment"),
    "metadata": {"name": "str"},
    "?description": "str",
    "lane": one_of(*LANES),
    "authority": {
        # The engine's whole safety property in one field. Anything other than
        # "none" is rejected at load, before a plan can be built on the promise.
        "clusterWrites": one_of("none"),
        "git": one_of("branch-and-pr", "none"),
        "?branchPrefix": "str",
        "?labels": map_of("str"),
    },
    "?credentialRefs": list_of("str"),
}

SLOT_LIBRARY_SPEC = {
    "apiVersion": "str",
    "kind": one_of("SlotLibrary"),
    "metadata": {"name": "str"},
    "slots": list_of(
        {
            "name": "str",
            "summary": "str",
            "node": one_of(*SLOT_NODES),
            "evidence": "str",
            "?requires": list_of("str"),
            "?producer": "str",
        },
        minimum=1,
    ),
}

REGISTRY_SPEC = {
    "apiVersion": "str",
    "kind": one_of("CatalogRegistry"),
    "metadata": {"owner": "str"},
    "?description": "str",
    "units": list_of(
        {
            "unit": "str",
            "?policy": "str",
            "?chartRef": "str",
            "?blueprintTemplate": "str",
            "?pinnedBy": one_of("platform", "unit"),
            "?tags": list_of("str"),
        },
        minimum=1,
    ),
}


class Definition:
    def __init__(self, path: str, raw: dict, library: dict):
        self.path = path
        self.raw = raw
        self.name = raw["metadata"]["name"]
        self.outputs = sorted(raw["outputs"], key=lambda o: o["name"])
        self.slots = _resolve_slots(self, library)
        self.unit_names = sorted({o["unit"] for o in self.outputs})
        self.view = canonical_view(raw)
        self.digest = digest(KIND_DEFINITION, self.view)

    def outputs_for(self, unit: str) -> list[dict]:
        return [o for o in self.outputs if o["unit"] == unit]


class Environment:
    def __init__(self, path: str, raw: dict):
        self.path = path
        self.raw = raw
        self.name = raw["metadata"]["name"]
        self.lane = raw["lane"]
        self.digest = digest(KIND_ENVIRONMENT, _digestable(raw))


class SlotLibrary:
    def __init__(self, path: str, raw: dict):
        self.path = path
        self.by_name = {}
        for slot in raw["slots"]:
            if slot["name"] in self.by_name:
                fail(E_SCHEMA, f"{path}: slot {slot['name']!r} declared twice")
            self.by_name[slot["name"]] = slot
        self.digest = digest("adoption.slots/v1", _digestable(raw))

    def require(self, name: str, where: str) -> dict:
        if name not in self.by_name:
            fail(
                E_SLOT_UNKNOWN,
                f"{where}: slot {name!r} is not defined by {self.path}",
                hint=f"known slots: {', '.join(sorted(self.by_name))}",
            )
        return self.by_name[name]


class Registry:
    def __init__(self, path: str, raw: dict):
        self.path = path
        self.raw = raw
        self.owner = raw["metadata"]["owner"]
        self.units = {u["unit"]: u for u in raw["units"]}
        self.digest = digest(KIND_REGISTRY, canonical_view(raw))


class Lock:
    def __init__(self, path: str | None, raw: dict | None, *, stale: bool = False):
        self.path = path
        self.raw = raw or {}
        self.stale = stale
        self.pins = {}
        for pin in (self.raw.get("pins") or []):
            self.pins[pin["unit"]] = pin
        self.registry_digest = self.raw.get("registryDigest")
        self.digest = lock_digest(self.raw) if raw else None


def lock_digest(body: dict) -> str:
    """The lock's identity. Pins are a set, so their order is not part of it."""
    return digest(KIND_LOCK, canonical_view(body))


# --------------------------------------------------------------------------- #


def load(path: str, kind_label: str, spec: dict, root: str) -> dict:
    full = os.path.join(root, path)
    if not os.path.exists(full):
        fail(E_INPUT_MISSING, f"{kind_label} not found: {path}")
    raw = read_yaml(path, cwd=root)
    if not isinstance(raw, dict):
        fail(E_SCHEMA, f"{path}: want a mapping at the document root")
    return validate(path, raw, spec)


def load_definition(path: str, root: str, library: SlotLibrary) -> Definition:
    raw = load(path, "definition", DEFINITION_SPEC, root)
    _reject_digests(path, raw)
    return Definition(path, raw, library)


def load_environment(path: str, root: str) -> Environment:
    raw = load(path, "environment", ENVIRONMENT_SPEC, root)
    return Environment(path, raw)


def load_slot_library(path: str, root: str) -> SlotLibrary:
    raw = load(path, "slot library", SLOT_LIBRARY_SPEC, root)
    lib = SlotLibrary(path, raw)
    for name, slot in lib.by_name.items():
        for req in slot.get("requires", []):
            if req not in lib.by_name:
                fail(E_SCHEMA, f"{path}: slot {name!r} requires unknown slot {req!r}")
            if req == name:
                fail(E_SCHEMA, f"{path}: slot {name!r} requires itself")
    return lib


def load_registry(path: str, root: str) -> Registry:
    raw = load(path, "catalog registry", REGISTRY_SPEC, root)
    _reject_digests(path, raw)
    return Registry(path, raw)


def load_lock(path: str | None, root: str, registry: Registry) -> Lock:
    """The lock must name the registry bytes it was generated against."""
    if not path:
        return Lock(None, None)
    full = os.path.join(root, path)
    if not os.path.exists(full):
        return Lock(None, None)
    raw = read_yaml(path, cwd=root)
    if not isinstance(raw, dict):
        fail(E_SCHEMA, f"{path}: want a mapping at the document root")
    if "apiVersion" in raw:
        fail(E_SCHEMA, f"{path}: generated records use schemaVersion, not apiVersion")
    if raw.get("schemaVersion") != KIND_LOCK:
        fail(E_SCHEMA, f"{path}: schemaVersion must be {KIND_LOCK!r}")
    recorded = raw.get("registryDigest")
    # Staleness is recorded, not raised here. Failing at load would mean the one
    # command that repairs a lock — `catalog pin` — could never run, because reading
    # the input it is meant to rewrite would abort first. `compile_plan` is where a
    # lock is actually relied on, and that is where it fails.
    return Lock(path, raw, stale=recorded != registry.digest)


def resolve_ref(from_path: str, ref: str) -> str:
    """Resolve a reference inside an authored file to a repo-relative path."""
    joined = os.path.normpath(os.path.join(os.path.dirname(from_path), ref))
    if joined.startswith(".."):
        fail(E_SCHEMA, f"{from_path}: reference {ref!r} escapes the repository")
    return joined.replace(os.sep, "/")


def write_lock(path: str, payload: str, root: str, expect: str | None) -> None:
    """Compare-and-swap write: refuse unless the current bytes are exactly `expect`."""
    full = os.path.join(root, path)
    current = None
    if os.path.exists(full):
        with open(full, encoding="utf-8") as handle:
            current = handle.read()
    if current != expect:
        fail(
            E_LOCK_STALE,
            f"{path}: the lock changed since it was read",
            hint="re-read the lock and re-run the bump; nothing was written",
        )
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(payload)


def _resolve_slots(definition: Definition, library: SlotLibrary) -> dict:
    """{slot name: library slot} for every slot any output names, checked up front."""
    out = {}
    for output in definition.outputs:
        for name in output["slots"]:
            out[name] = library.require(name, f"{definition.path}:{output['name']}")
    return out


def _reject_digests(path: str, node, trail: str = "") -> None:
    if isinstance(node, str):
        if "@sha256:" in node or (trail.endswith(".digest") and node.startswith("sha256:")):
            fail(
                E_REGISTRY_DIGEST,
                f"{path}{trail}: digests do not belong in authored catalog input",
                hint="record digests in pins.lock.yaml via `adoption catalog pin`",
            )
    elif isinstance(node, dict):
        for key, value in node.items():
            _reject_digests(path, value, f"{trail}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _reject_digests(path, value, f"{trail}[{index}]")


def _digestable(raw: dict) -> dict:
    """A copy with comment-shaped keys removed, so a comment cannot change identity."""
    return {k: v for k, v in raw.items() if not str(k).startswith("#")}


def canonical_view(raw: dict) -> dict:
    """The record as identity sees it.

    A Definition's `outputs` and a registry's `units` are sets, not sequences: the
    engine never assigns meaning to the order they are listed in, so reordering
    them — by hand, or by a merge that interleaves two branches — must not read as a
    new desired state. Every other field is preserved verbatim.
    """
    out = _digestable(raw)
    for field, key in (("outputs", "name"), ("units", "unit"), ("slots", "name"), ("pins", "unit")):
        if isinstance(out.get(field), list):
            out[field] = sorted(out[field], key=lambda item: str(item.get(key, "")) if isinstance(item, dict) else str(item))
    return out
