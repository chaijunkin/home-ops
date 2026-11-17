#!/usr/bin/env python3
"""Plan compilation: Definition + Environment + Catalog -> a canonical graph.

A Plan describes work; it does not prove execution. It carries no authority, and
`authority: description-only` is written into it so a transcript cannot quote a
green plan as a deployment.

Two things make the digest trustworthy:

* Desired state is separated from incidental identity. T1 (inside
  `desiredState`) is what decides the answer: definition, environment, resolved
  slot set, unit set, engine version. T2 (excluded) is the digest itself and
  anything derived from it. A transport locator — a URL, a registry host, a
  kubeconfig path — is never T1, or every credential rotation would invalidate
  every adoption claim.
* Every collection is sorted before serialisation, so two compiles of the same
  checkout are byte-identical. Ordering comes from the graph, never from a
  directory walk or a dict.
"""

from __future__ import annotations

from canonical import KIND_PLAN, digest, sortable
from errors import E_GRAPH_CYCLE, E_LANE_VIOLATION, E_LOCK_STALE, E_PIN_MISSING, fail
from inputs import Definition, Environment, Lock, Registry, SlotLibrary
from repo import ks_name_index, unit_dependencies, require_units

ENGINE_VERSION = "0.1.0"
SCHEMA_VERSION = KIND_PLAN


LANE_NODE_CEILING = {
    # A node kind is only available at a lane that can actually attest to it.
    # `observe` needs live read access and belongs to the deferred reconciled lane,
    # so no lane shipped today admits it — that is the point, not an oversight.
    "static": {"discover", "render", "verify", "diff"},
    "proposed": {"discover", "render", "verify", "diff", "propose"},
}


def compile_plan(
    root: str,
    definition: Definition,
    environment: Environment,
    library: SlotLibrary,
    registry: Registry,
    lock: Lock,
) -> dict:
    """Build the plan. Nothing here writes, applies, or opens anything."""
    require_units(root, definition.unit_names)
    _require_lane(definition, environment, library)
    _require_lock_fresh(lock)
    _require_lock_coverage(definition, registry, lock)

    index = {name: name for name in definition.unit_names}
    ks_index = _ks_subset(root, definition.unit_names)
    nodes: dict[str, dict] = {}
    for output in definition.outputs:
        for slot_name in sorted(output["slots"], key=str):
            slot = library.by_name[slot_name]
            node_id = f"{output['name']}/{slot_name}"
            nodes[node_id] = {
                "id": node_id,
                "kind": slot["node"],
                "output": output["name"],
                "unit": output["unit"],
                "slot": slot_name,
                "summary": slot["summary"],
                "evidence": slot["evidence"],
                "requires": [],
            }

    # Intra-output edges: a slot waits for the slots the library says it needs.
    for output in definition.outputs:
        named = set(output["slots"])
        for slot_name in sorted(named):
            for req in sorted(library.by_name[slot_name].get("requires", [])):
                if req in named:
                    _edge(nodes, f"{output['name']}/{slot_name}", f"{output['name']}/{req}")

    # Cross-unit edges from Flux ordering. A unit's work waits for the unit it
    # depends on to at least be resolved, so a manifest is never edited before
    # the thing it calls exists.
    for unit in definition.unit_names:
        downstream = _outputs_of(definition, unit)
        for dep in unit_dependencies(root, unit, ks_index):
            if dep not in index:
                continue  # a dependency outside this plan is not this plan's business
            for target in _resolve_dependency_target(definition, dep):
                for output in downstream:
                    for slot_name, node in sorted(nodes.items()):
                        if node["output"] != output["name"] or node["slot"] == "inventory":
                            continue
                        _edge(nodes, node["id"], target)

    order = _toposort(nodes)
    _assert_no_cycle(nodes, order)

    outputs = [
        {
            "name": o["name"],
            "unit": o["unit"],
            "slots": sorted(o["slots"]),
            "nodes": sorted(n["id"] for n in nodes.values() if n["output"] == o["name"]),
        }
        for o in sorted(definition.outputs, key=sortable("name"))
    ]

    desired_state = {
        "engineVersion": ENGINE_VERSION,
        "definition": definition.view,
        # `credentialRefs` is stripped deliberately. A credential reference is a
        # transport locator, and a transport locator inside desired-state identity
        # means every secret rotation invalidates every adoption claim built on it.
        # The Environment is still fully identified by its own `environmentDigest`.
        "environment": _identity_of(environment.raw),
        "slotLibrary": sorted(library.by_name),
        "slotEvidence": {n: library.by_name[n]["evidence"] for n in sorted(library.by_name)},
        "unitSet": sorted(definition.unit_names),
        "outputs": outputs,
        "registryOwner": registry.owner,
        "registryDigest": registry.digest,
    }
    body = {
        "schemaVersion": SCHEMA_VERSION,
        "definitionName": definition.name,
        "definitionDigest": definition.digest,
        "environmentName": environment.name,
        "environmentDigest": environment.digest,
        "slotLibraryDigest": library.digest,
        "registryDigest": registry.digest,
        "lockDigest": lock.digest if lock.raw else None,
        "lane": environment.lane,
        # Nothing in this record authorises a change. Execution reads the plan;
        # the plan never reads back as permission.
        "authority": "description-only",
        "desiredState": desired_state,
        "desiredStateDigest": digest("adoption.desired-state/v1", desired_state),
        "outputs": outputs,
        "nodes": sorted(nodes.values(), key=sortable("id")),
        # Each edge carries its own stable key. Without one, an array of edges is
        # addressed by position, so adding an edge renumbers every later edge and a
        # review shows the whole graph as replaced.
        "edges": sorted(
            ({"key": f"{n['id']}->{req}", "from": n["id"], "to": req, "type": "requires"}
             for n in nodes.values() for req in n["requires"]),
            key=sortable("from", "to"),
        ),
        "order": order,
    }
    body["planDigest"] = digest(KIND_PLAN, body)
    return body


def plan_filename(plan: dict) -> str:
    return plan["planDigest"].replace(":", "-") + ".json"


TRANSPORT_KEYS = {"credentialrefs", "kubeconfig", "webhook"}
TRANSPORT_SUFFIXES = ("url", "uri")


def _identity_of(node):
    """Drop transport locators from a record so identity survives credential rotation."""
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            lowered = str(key).lower()
            if lowered in TRANSPORT_KEYS or lowered.endswith(TRANSPORT_SUFFIXES):
                continue
            out[key] = _identity_of(value)
        return out
    if isinstance(node, list):
        return [_identity_of(item) for item in node]
    return node


def _edge(nodes: dict, source: str, target: str) -> None:
    if target not in nodes or source == target:
        return
    requires = nodes[source]["requires"]
    if target not in requires:
        requires.append(target)


def _outputs_of(definition: Definition, unit: str) -> list[dict]:
    return [o for o in definition.outputs if o["unit"] == unit]


def _resolve_dependency_target(definition: Definition, dep_unit: str) -> list[str]:
    """The node(s) a dependent unit waits on: its inventory slot if it has one."""
    targets = []
    for output in _outputs_of(definition, dep_unit):
        if "inventory" in output["slots"]:
            targets.append(f"{output['name']}/inventory")
    return targets


def _ks_subset(root: str, units: list[str]) -> dict[str, str]:
    """{ks name: unit} limited to units in play, so dependsOn resolves locally."""
    index = ks_name_index(root)
    allowed = set(units)
    return {name: unit for name, unit in index.items() if unit in allowed}


def _require_lane(definition: Definition, environment: Environment, library: SlotLibrary) -> None:
    """The Environment sets the claim ceiling; a Definition cannot raise its own."""
    allowed = LANE_NODE_CEILING[environment.lane]
    offending = sorted(
        {
            f"{slot_name}({library.by_name[slot_name]['node']})"
            for slot_name in definition.slots
            if library.by_name[slot_name]["node"] not in allowed
        }
    )
    if offending:
        fail(
            E_LANE_VIOLATION,
            f"lane {environment.lane!r} from {environment.path} does not permit: "
            + ", ".join(offending),
            hint=f"allowed node kinds at this lane: {', '.join(sorted(allowed))}",
        )


def _require_lock_fresh(lock: Lock) -> None:
    """A plan built on pins from a different registry would state the wrong intent."""
    if lock.stale:
        fail(
            E_LOCK_STALE,
            f"{lock.path}: pins were generated against a different registry",
            hint="run `adoption catalog pin` to regenerate the lock, then `adoption plan`",
        )


def _require_lock_coverage(definition: Definition, registry: Registry, lock: Lock) -> None:
    """A plan whose pins are unknown is not a plan; it is a guess."""
    if not lock.raw:
        return
    missing = [
        o["unit"]
        for o in definition.outputs
        if registry.units.get(o["unit"], {}).get("pinnedBy")
        and o["unit"] not in lock.pins
    ]
    if missing:
        fail(
            E_PIN_MISSING,
            f"the lock has no pins for: {', '.join(sorted(missing))}",
            hint="run `adoption catalog pin` to generate pins.lock.yaml",
        )


def _toposort(nodes: dict) -> list[str]:
    """Kahn's algorithm, ties broken by node id so the order is reproducible."""
    indegree = {node_id: len(node["requires"]) for node_id, node in nodes.items()}
    dependents: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for node_id, node in nodes.items():
        for req in node["requires"]:
            dependents[req].append(node_id)
    ready = sorted(node_id for node_id, deg in indegree.items() if deg == 0)
    order: list[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        newly = []
        for dependent in dependents[current]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                newly.append(dependent)
        if newly:
            ready = sorted(ready + newly)
    return order


def _assert_no_cycle(nodes: dict, order: list[str]) -> None:
    if len(order) == len(nodes):
        return
    stuck = sorted(set(nodes) - set(order))
    fail(
        E_GRAPH_CYCLE,
        f"dependency cycle among: {', '.join(stuck[:8])}"
        + (f" (+{len(stuck) - 8} more)" if len(stuck) > 8 else ""),
        hint="a slot's `requires`, or a Flux dependsOn pair, points around a loop",
    )
