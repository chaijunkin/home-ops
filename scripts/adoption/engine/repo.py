#!/usr/bin/env python3
"""Fleet facts the compiler reads: units, Flux ordering, and what each unit pins.

The unit is the directory holding a `ks.yaml`. That is what Flux reconciles, what
`dependsOn` names, and what a pull request touches, so it is also the granularity
adoption is claimed at.

Only tracked files are read. Uncommitted scratch must not change a plan digest,
otherwise "the plan is stable" would be a claim about a working tree.
"""

from __future__ import annotations

import os
import subprocess

from errors import E_UNIT_UNKNOWN, fail
from yamlio import decode_stream, run_yq

APPS_SCOPE = "kubernetes/apps/"

# A non-mapping document cannot be a Kubernetes resource, and this estate tracks
# YAML whose root is a sequence (Ansible playbooks, a webhook hooks config). yq
# refuses to index an array with `kind`, so unguarded expressions abort an entire
# multi-file scan on one unrelated file. Filtering on type first is a semantic
# statement, not leniency.
MAP_DOC = 'select(type == "!!map")'


def tracked_files(root: str, *prefixes: str) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "HEAD", "--name-only"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        fail(2, f"git ls-tree failed: {proc.stderr.strip()[:200]}")
    wanted = prefixes or (APPS_SCOPE,)
    return sorted(
        p for p in proc.stdout.splitlines()
        if p.endswith((".yaml", ".yml")) and p.startswith(wanted)
    )


def unit_dirs(root: str) -> list[str]:
    return sorted({os.path.dirname(p) for p in tracked_files(root) if os.path.basename(p) == "ks.yaml"})


def require_units(root: str, units: list[str]) -> None:
    """Capability admission: every named unit must exist before anything is read."""
    known = set(unit_dirs(root))
    missing = [u for u in units if u not in known]
    if missing:
        fail(
            E_UNIT_UNKNOWN,
            f"{len(missing)} unit(s) named by the Definition do not exist: {', '.join(missing)}",
            hint=f"{len(known)} units are known; `adoption catalog show` lists them",
        )


def ks_name_index(root: str) -> dict[str, str]:
    """{Kustomization name: unit dir}, so `dependsOn` names resolve to units.

    The projection is an object, not `[a, b][]`: yq flattens that form into two
    separate scalars, which silently produced an empty index and therefore no
    cross-unit edges at all.
    """
    ks_paths = [p for p in tracked_files(root) if os.path.basename(p) == "ks.yaml"]
    if not ks_paths:
        return {}
    out = run_yq(f'{MAP_DOC} | {{"n": .metadata.name, "f": fileName}}', *ks_paths, cwd=root)
    index: dict[str, str] = {}
    for record in decode_stream(out):
        if not isinstance(record, dict):
            continue
        name, path = record.get("n"), record.get("f")
        if isinstance(name, str) and isinstance(path, str):
            index[name] = os.path.dirname(path.replace(os.sep, "/"))
    return index


def unit_dependencies(root: str, unit: str, index: dict[str, str]) -> list[str]:
    """Units this one waits on, resolved through ks names, self-references dropped."""
    ks = os.path.join(root, unit, "ks.yaml")
    if not os.path.exists(ks):
        return []
    out = run_yq(
        '.spec.dependsOn // [] | .[].name', os.path.join(unit, "ks.yaml"), cwd=root
    )
    deps = {index[v] for v in decode_stream(out) if isinstance(v, str) and v in index}
    return sorted(d for d in deps if d != unit)


_OCI_CACHE: dict[str, dict[str, dict]] = {}


def oci_index(root: str) -> dict[str, list[dict]]:
    """{OCIRepository name: [every definition of that name]} across `kubernetes/`.

    A unit's `chartRef` almost never points at a source defined inside the unit:
    the estate defines `app-template` under `kubernetes/components/common/repos/`
    and 86 HelmReleases refer to it. Resolving a chart therefore needs the wider
    tree, and filenames are no clue (the same string appears as `chartRef.kind`), so
    every tracked YAML under `kubernetes/` is read once and filtered by `kind`.

    Every definition is kept, not the first one found. `app-template` and
    `snapshot-controller` are each defined twice in this estate, and picking one
    silently would let the lock state a resolution the repository does not support.
    The effective namespace would disambiguate exactly, but that needs `kustomize
    build`; the lock records the ambiguity and the file paths instead, which a
    reviewer can check without running anything.
    """
    if root in _OCI_CACHE:
        return _OCI_CACHE[root]
    paths = tracked_files(root, "kubernetes/")
    index: dict[str, list[dict]] = {}
    if paths:
        out = run_yq(
            f'{MAP_DOC} | select(.kind == "OCIRepository") | '
            '{"n": .metadata.name, "definedIn": fileName, '
            '"url": .spec.url, "tag": .spec.ref.tag, "digest": .spec.ref.digest}',
            *paths,
            cwd=root,
        )
        for record in decode_stream(out):
            if not isinstance(record, dict) or not isinstance(record.get("n"), str):
                continue
            record["definedIn"] = str(record.get("definedIn") or "").replace(os.sep, "/")
            index.setdefault(record["n"], []).append(record)
    for definitions in index.values():
        definitions.sort(key=lambda item: item["definedIn"])
    _OCI_CACHE[root] = index
    return index


def unit_pins(root: str, unit: str) -> dict:
    """What a unit currently points at, for the lock.

    This estate has 161 HelmReleases that reference a chart through
    `spec.chartRef: {kind: OCIRepository, name: app-template}` and none that inline
    `spec.chart.spec`. So the chart a unit installs is identified by the name it
    refers to, and the version lives in the OCIRepository object — usually one
    object shared by many units, which is precisely a derived pin set. A reference
    that resolves to nothing is recorded as `resolved: null` rather than dropped:
    an unresolvable chart is a fact a reviewer needs, not a detail.

    Images are collected once per container, not once per field: the map form
    `image: {image: ghcr.io/x, tag: 1.2.3@sha256:…}` is one reference, and pinning
    a chart does not pin the images that chart pulls, so each image is its own
    lock member.
    """
    files = [p for p in tracked_files(root, unit + "/")]
    if not files:
        return {"charts": [], "images": []}
    sources = oci_index(root)
    out = run_yq('{"f": fileName, "d": .}', *files, cwd=root)
    charts: list[dict] = []
    images: list[dict] = []
    for record in decode_stream(out):
        if not isinstance(record, dict):
            continue
        doc = record.get("d")
        if not isinstance(doc, dict):
            continue
        spec = doc.get("spec") or {}
        if doc.get("kind") == "HelmRelease":
            for ref in _chart_refs(spec):
                charts.append(_resolve_chart(ref, sources.get(ref["name"], [])))
        for ref in _image_refs(spec):
            images.append({"ref": ref})
    return {
        "charts": sorted({c["chartRef"]: c for c in charts}.values(), key=lambda c: c["chartRef"]),
        "images": [{"ref": ref} for ref in sorted({i["ref"] for i in images})],
    }


def _resolve_chart(ref: dict, definitions: list[dict]) -> dict:
    """One chart reference as the lock records it, ambiguity included.

    A name with no definition resolves to null and is kept: an unresolvable chart is
    a fact a reviewer needs, not a detail. A name defined more than once resolves
    only when every definition points at the same bytes; otherwise the candidates
    are listed, because the lock cannot say which one Flux would install without
    evaluating namespaces. An inline `chart.spec` carries its own version and needs
    no source object at all.
    """
    entry = {
        "chartRef": f"{ref['kind']}/{ref['name']}",
        "definedIn": sorted({item["definedIn"] for item in definitions}),
    }
    if not definitions:
        if ref.get("selfResolved"):
            entry["resolved"] = ref["selfResolved"]
            entry["resolutionKind"] = (
                "digest" if "@sha256:" in ref["selfResolved"] else "tag"
            )
        else:
            entry["resolved"] = None
            entry["resolutionKind"] = "none"
        return entry
    resolutions = sorted({_resolution(item) for item in definitions})
    if len(resolutions) == 1:
        entry["resolved"] = resolutions[0]
    else:
        entry["resolved"] = None
        entry["ambiguous"] = resolutions
    kinds = {_resolution_kind(item) for item in definitions}
    # Weakest kind wins: two definitions of one name, one by digest and one by tag,
    # do not add up to a pinned chart.
    entry["resolutionKind"] = "digest" if kinds == {"digest"} else ("tag" if "tag" in kinds else "none")
    return entry


def _resolution(definition: dict) -> str:
    """`url@target`, or the bare url when the source names no target at all.

    A source object with neither `ref.tag` nor `ref.digest` leaves Flux to resolve
    the default, so the honest record is the url with nothing appended. Writing
    `@unresolved` there would read like a real reference, and a lock entry that
    looks copyable is worse than one that looks incomplete.
    """
    url = str(definition.get("url") or "")
    target = definition.get("digest") or definition.get("tag")
    return f"{url}@{target}" if target else url


def _resolution_kind(definition: dict) -> str:
    """Whether a chart source names immutable bytes or a mutable tag.

    This estate points `app-template` at `…@5.3.0`, a tag that a publisher can
    repoint. The lock is the record of what is pinned, so it has to say which of its
    entries are not. Pinning a chart source would also not pin the images that chart
    pulls, and those are the `digest-pinned` slot's business, not this file's.
    """
    if definition.get("digest"):
        return "digest"
    if "@sha256:" in str(definition.get("url") or ""):
        return "digest"
    if definition.get("tag"):
        return "tag"
    return "none"


def _chart_refs(spec: dict) -> list[dict]:
    """Both chart shapes: `chartRef` (this estate) and inline `chart.spec` (portable)."""
    found: list[dict] = []
    ref = spec.get("chartRef")
    if isinstance(ref, dict) and isinstance(ref.get("name"), str):
        found.append({"kind": str(ref.get("kind") or "HelmChart"), "name": ref["name"]})
    inline = (spec.get("chart") or {}).get("spec") if isinstance(spec.get("chart"), dict) else None
    if isinstance(inline, dict) and isinstance(inline.get("chart"), str):
        version = str(inline.get("version") or "unversioned")
        found.append({
            "kind": "inline",
            "name": f"{inline['chart']}@{version}",
            "selfResolved": f"{inline['chart']}@{version}",
        })
    return found


def _image_refs(node):
    """Yield one string per container image reference, map form included."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "image":
                if isinstance(value, str):
                    if value.strip():
                        yield value.strip()
                elif isinstance(value, dict):
                    repo = value.get("image") or value.get("repository")
                    if isinstance(repo, str) and repo.strip():
                        tag = value.get("tag")
                        digest_ = value.get("digest")
                        ref = repo.strip()
                        if isinstance(tag, str) and tag.strip():
                            ref += f":{tag.strip()}"
                        if isinstance(digest_, str) and digest_.strip():
                            ref += f"@{digest_.strip()}"
                        yield ref
            elif key in ("repository", "repo") and isinstance(value, str) and value.strip():
                # three-field charts keep the digest in its own key
                if "tag" in node or "digest" in node:
                    continue  # already yielded by the enclosing image node, or not ours
            else:
                yield from _image_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _image_refs(item)
