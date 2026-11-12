#!/usr/bin/env python3
"""Adoption engine command surface.

The machine contract, adopted because an agent that parses prose cannot be audited:

* stdout carries exactly one canonical JSON document (or the `--out` file), never a
  log line; diagnostics, progress, and error prose go to stderr.
* `--pretty` is display-only and never canonical input.
* exit codes follow the published bands in `engine/errors.py`.
* capability admission happens before any output: an unknown unit, slot, or lane is
  a coded error with no partial result left behind to be mistaken for a finding.

Phase A is compile-and-inspect: `plan`, `graph`, `diff`, `catalog`. Execution is a
separate verb in Phase B precisely because it is a separate authority.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import traceback

from canonical import KIND_LOCK, KIND_PLAN, canonical_json, digest, pretty
from diffing import diff
from errors import (
    E_DIFF,
    E_INPUT_MISSING,
    E_INTERNAL,
    E_USAGE,
    EXIT_DIFF,
    EXIT_OK,
    NAMES,
    AdoptionError,
    fail,
)
from inputs import (
    Lock,
    load_definition,
    load_environment,
    load_lock,
    load_registry,
    load_slot_library,
    lock_digest,
    resolve_ref,
    write_lock,
)
from plan import compile_plan, plan_filename
from repo import unit_pins
from views import render
from yamlio import read_yaml

PLANS_DIR = ".adoption/plans"
SLOT_LIBRARY = "adoption/slots.yaml"


class Context:
    """Everything a verb needs, resolved and validated once, before any output."""

    def __init__(self, root: str, definition_path: str | None):
        self.root = root
        self.library = load_slot_library(SLOT_LIBRARY, root)
        self.definition_path = definition_path or self._only_definition()
        self.definition = load_definition(self.definition_path, root, self.library)
        self.environment_path = resolve_ref(self.definition_path, self.definition.raw["environment"])
        self.environment = load_environment(self.environment_path, root)
        base = resolve_ref(self.definition_path, self.definition.raw["catalog"]["base"])
        self.registry_path = f"{base}/registry.yaml"
        self.registry = load_registry(self.registry_path, root)
        # An authored `catalog.lock` is relative to the Definition; the default is
        # already repo-relative from `base`. Resolving the default a second time
        # would graft it onto the Definition's directory.
        authored_lock = self.definition.raw["catalog"].get("lock")
        self.lock_path = (
            resolve_ref(self.definition_path, authored_lock) if authored_lock
            else f"{base}/pins.lock.yaml"
        )
        self.lock: Lock = load_lock(self.lock_path, root, self.registry)

    def _only_definition(self) -> str:
        found = sorted(glob.glob(os.path.join(self.root, "adoption/definitions/*/*.yaml")))
        rel = [os.path.relpath(p, self.root).replace(os.sep, "/") for p in found]
        if not rel:
            fail(
                E_INPUT_MISSING,
                "no Definition found under adoption/definitions/*/",
                hint="pass --definition adoption/definitions/<family>/<name>.yaml",
            )
        if len(rel) > 1:
            fail(
                E_USAGE,
                f"{len(rel)} Definitions exist; name one with --definition",
                hint="candidates: " + ", ".join(rel),
            )
        return rel[0]

    def plan(self) -> dict:
        return compile_plan(
            self.root, self.definition, self.environment, self.library, self.registry, self.lock
        )


# --------------------------------------------------------------------------- #


def verb_plan(ctx: Context, args) -> int:
    plan = ctx.plan()
    rel = f"{PLANS_DIR}/{plan_filename(plan)}"
    payload = canonical_json(plan).decode("utf-8") + "\n"

    if args.check:
        _check_plans(ctx, plan, rel, payload)
        _emit({"status": "current", "planDigest": plan["planDigest"], "path": rel}, args.pretty)
        return EXIT_OK

    target = args.out or rel
    full = os.path.join(ctx.root, target)
    existed = os.path.exists(full)
    if not existed or _read(full) != payload:
        _write(full, payload)
    # A plan is a pure function of current inputs, so any other file in the plans
    # directory has been superseded. Leaving it means a reviewer cannot tell which
    # plan is current, and `--check` would certify a directory full of history.
    pruned = _prune_superseded(ctx, {rel}) if not args.out else 0
    _emit(
        {
            "status": "unchanged" if existed and _read(full) == payload else "written",
            "planDigest": plan["planDigest"],
            "desiredStateDigest": plan["desiredStateDigest"],
            "lane": plan["lane"],
            "definition": ctx.definition.name,
            "environment": ctx.environment.name,
            "outputs": len(plan["outputs"]),
            "nodes": len(plan["nodes"]),
            "edges": len(plan["edges"]),
            "path": target,
            "prunedSuperseded": pruned,
        },
        args.pretty,
    )
    return EXIT_OK


def _prune_superseded(ctx: Context, keep: set[str]) -> int:
    removed = 0
    for existing in glob.glob(os.path.join(ctx.root, PLANS_DIR, "*.json")):
        shown = os.path.relpath(existing, ctx.root).replace(os.sep, "/")
        if shown in keep:
            continue
        os.remove(existing)
        removed += 1
        print(f"pruned superseded plan {shown}", file=sys.stderr)
    return removed


def _check_plans(ctx: Context, plan: dict, rel: str, payload: str) -> None:
    """Stale and hand-edited are different failures; a plan's name is part of its proof.

    Each committed file is addressed by the digest of its own contents, so editing
    bytes inside a plan breaks the name/content agreement immediately — the check
    does not need a copy of the original to notice.
    """
    for existing in sorted(glob.glob(os.path.join(ctx.root, PLANS_DIR, "*.json"))):
        shown = os.path.relpath(existing, ctx.root).replace(os.sep, "/")
        try:
            recorded = json.loads(_read(existing))
        except ValueError:
            fail(E_DIFF, f"{shown}: is not valid JSON")
        if not isinstance(recorded, dict):
            fail(E_DIFF, f"{shown}: want a JSON object")
        named = os.path.basename(existing)[: -len(".json")].replace("-", ":", 1)
        stripped = {k: v for k, v in recorded.items() if k != "planDigest"}
        actual = digest(KIND_PLAN, stripped)
        if actual != named:
            fail(
                E_DIFF,
                f"{shown}: its name claims {named} but its contents hash to {actual}",
                hint="generated plans are never hand-edited; re-run `adoption plan`",
            )
    if not os.path.exists(os.path.join(ctx.root, rel)):
        fail(E_DIFF, f"{rel} is missing: the compiled plan has not been committed",
             hint="run `adoption plan` and commit the result")
    if _read(os.path.join(ctx.root, rel)) != payload:
        fail(E_DIFF, f"{rel} does not match the current inputs")


def verb_graph(ctx: Context, args) -> int:
    plan = ctx.plan()
    text = render(plan, args.format, args.output)
    if not text.endswith("\n"):
        text += "\n"
    if args.out:
        _write(os.path.join(ctx.root, args.out), text)
        _emit({"status": "written", "path": args.out, "format": args.format}, args.pretty)
    else:
        sys.stdout.write(text)
    return EXIT_OK


def verb_diff(root: str, args) -> int:
    before = _read_json(args.before, root)
    after = _read_json(args.after, root)
    result = diff(before, after, include_volatile=args.include_volatile)
    result["kind"] = "plan-diff"
    _emit(result, args.pretty)
    return EXIT_OK if result["identical"] else EXIT_DIFF


def verb_catalog(ctx: Context, args) -> int:
    if args.subcommand == "show":
        return _catalog_show(ctx, args)
    if args.subcommand == "pin":
        return _catalog_pin(ctx, args)
    return _catalog_bump(ctx, args)


def _catalog_show(ctx: Context, args) -> int:
    units = sorted(ctx.registry.units)
    _emit(
        {
            "kind": "catalog",
            "owner": ctx.registry.owner,
            "registryPath": ctx.registry.path,
            "registryDigest": ctx.registry.digest,
            "lockPath": ctx.lock_path,
            "lockExists": bool(ctx.lock.raw),
            "lockDigest": ctx.lock.digest,
            "units": len(units),
            "pinned": len(ctx.lock.pins),
            "unpinned": sorted(u for u in units if u not in ctx.lock.pins),
        },
        args.pretty,
    )
    return EXIT_OK


def _catalog_pin(ctx: Context, args) -> int:
    """Generate the lock from tracked state; a chart shared by 2+ units becomes a derived set.

    Facts are read once per unit and then grouped, because the shared-chart question
    is a join over that table, not a lookup per (unit, unit) pair.
    """
    facts = {unit: unit_pins(ctx.root, unit) for unit in sorted(ctx.registry.units)}
    # A chart source shared by two or more units is one pin that moves them all.
    users: dict[str, int] = {}
    for found in facts.values():
        for chart in found["charts"]:
            users[chart["chartRef"]] = users.get(chart["chartRef"], 0) + 1

    members = []
    unresolvable = []
    floating = []
    for unit in sorted(facts):
        found = facts[unit]
        member = {"unit": unit, "charts": found["charts"], "images": found["images"]}
        shared = sorted(ref for ref, count in users.items() if count >= 2 and
                        any(chart["chartRef"] == ref for chart in found["charts"]))
        # `none` rather than `unit` when the unit owns no chart at all: `unit` would
        # tell a reviewer there is a pin to bump when there is nothing there. Some
        # units are operator-managed and install no chart of their own.
        member["pinnedBy"] = ("platform" if shared else "unit") if found["charts"] else "none"
        if shared:
            member["derivedFrom"] = shared
        for chart in found["charts"]:
            if chart["resolved"] is None:
                unresolvable.append(f"{unit} {chart['chartRef']}")
            elif chart.get("resolutionKind") != "digest":
                floating.append(f"{unit} {chart['chartRef']} -> {chart['resolved']}")
        members.append(member)

    body = {
        "schemaVersion": KIND_LOCK,
        "generatedBy": "adoption/catalog",
        "registryDigest": ctx.registry.digest,
        "pins": sorted(members, key=lambda m: m["unit"]),
    }
    payload = pretty(body) + "\n"
    digest_of_lock = lock_digest(body)
    full = os.path.join(ctx.root, ctx.lock_path)

    if args.check:
        if not os.path.exists(full):
            fail(E_DIFF, f"{ctx.lock_path} does not exist yet", hint="run `adoption catalog pin`")
        if _lock_digest_at(full) != digest_of_lock:
            fail(E_DIFF, f"{ctx.lock_path} is not current", hint="run `adoption catalog pin`")
        _emit({"status": "current", "lockDigest": digest_of_lock, "path": ctx.lock_path}, args.pretty)
        return EXIT_OK

    prior = _read(full) if os.path.exists(full) else None
    write_lock(ctx.lock_path, payload, ctx.root, expect=prior)
    _emit(
        {
            "status": "written",
            "path": ctx.lock_path,
            "lockDigest": digest_of_lock,
            "members": len(members),
            "derivedMembers": sum(1 for m in members if m["pinnedBy"] == "platform"),
            # A member whose chart cannot be named is not a pinned member. Reported
            # here so `catalog pin` never looks like a clean result while carrying a
            # reference the repository cannot resolve. A resolution by tag rather
            # than digest is listed separately: it is legitimate today, and it is
            # still not a pin, so the lock must not imply one.
            "unresolvableCharts": sorted(unresolvable),
            "floatingChartResolutions": sorted(floating),
        },
        args.pretty,
    )
    return EXIT_OK


def _catalog_bump(ctx: Context, args) -> int:
    """Drift check only: tracked state versus what the lock recorded."""
    if not ctx.lock.raw:
        fail(E_DIFF, f"{ctx.lock_path} does not exist", hint="run `adoption catalog pin` first")
    drifted = []
    for unit in sorted(ctx.lock.pins):
        fresh = unit_pins(ctx.root, unit)
        recorded = ctx.lock.pins[unit]
        if fresh != {
            "charts": recorded.get("charts", []),
            "images": recorded.get("images", []),
        }:
            drifted.append(unit)
    _emit(
        {"kind": "bump-check", "lockDigest": ctx.lock.digest,
         "drifted": sorted(drifted), "count": len(drifted)},
        args.pretty,
    )
    return EXIT_OK if not drifted else EXIT_DIFF


# --------------------------------------------------------------------------- #


def _emit(payload: dict, pretty_output: bool) -> None:
    text = pretty(payload) if pretty_output else canonical_json(payload).decode("utf-8")
    sys.stdout.write(text + "\n")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _read_json(path: str, root: str) -> dict:
    full = path if os.path.isabs(path) else os.path.join(root, path)
    if not os.path.exists(full):
        fail(E_INPUT_MISSING, f"no such plan file: {path}")
    try:
        value = json.loads(_read(full))
    except ValueError as exc:
        fail(E_USAGE, f"{path}: not valid JSON ({exc})")
    if not isinstance(value, dict):
        fail(E_USAGE, f"{path}: want a JSON object")
    return value


def _lock_digest_at(path: str) -> str | None:
    """Hash a lock by its parsed contents, so restyling the file is not a pin change."""
    try:
        body = read_yaml(path)
    except AdoptionError:
        return None
    return lock_digest(body) if isinstance(body, dict) else None


def _write(full: str, text: str) -> None:
    parent = os.path.dirname(os.path.normpath(full))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(text)


def _root() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    if proc.returncode != 0:
        fail(E_USAGE, "adoption must run inside a git work tree")
    return proc.stdout.strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adoption",
        description="Declarative adoption engine: Definition -> Plan -> Run -> evidence.",
    )
    parser.add_argument("--root", default=None, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="verb", required=True)

    def common(p):
        p.add_argument("--definition", help="adoption/definitions/<family>/<name>.yaml")
        p.add_argument("--pretty", action="store_true", help="display only; never canonical input")

    plan_cmd = sub.add_parser("plan", help="compile the plan, or verify committed plans")
    common(plan_cmd)
    plan_cmd.add_argument("--check", action="store_true", help="byte-exact comparison, exit 3 on drift")
    plan_cmd.add_argument("--out", help="write the canonical plan here instead of .adoption/plans/")

    graph_cmd = sub.add_parser("graph", help="render the dependency graph")
    common(graph_cmd)
    graph_cmd.add_argument("--format", choices=("mermaid", "dot", "json"), default="mermaid")
    graph_cmd.add_argument("--output", metavar="NAME", help="limit the view to one named output")
    graph_cmd.add_argument("--out")

    diff_cmd = sub.add_parser("diff", help="compare two compiled plans")
    diff_cmd.add_argument("--before", required=True)
    diff_cmd.add_argument("--after", required=True)
    diff_cmd.add_argument("--include-volatile", action="store_true", help="compare digest fields too")
    diff_cmd.add_argument("--pretty", action="store_true")

    catalog_cmd = sub.add_parser("catalog", help="inspect or regenerate the catalog lock")
    catalog_cmd.add_argument("subcommand", choices=("show", "pin", "bump"), nargs="?", default="show")
    common(catalog_cmd)
    catalog_cmd.add_argument("--check", action="store_true")
    return parser


HANDLERS = {"plan": verb_plan, "graph": verb_graph, "catalog": verb_catalog}


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exit_request:
        # argparse reports usage as prose on stderr and exits 2. The published
        # contract promises one JSON document on stdout for every outcome, so a bad
        # flag has to arrive the same way as any other failure.
        code = exit_request.code if isinstance(exit_request.code, int) else E_USAGE
        if code == 0:  # --help and --version are successes with their own output
            return 0
        _emit(
            {
                "error": NAMES[E_USAGE],
                "code": E_USAGE,
                "detail": "argument parsing failed; see usage on stderr",
                "hint": "run `adoption --help` or `adoption <verb> --help`",
            },
            False,
        )
        return E_USAGE
    root = args.root or _root()
    try:
        if args.verb == "diff":
            return verb_diff(root, args)
        return HANDLERS[args.verb](Context(root, getattr(args, "definition", None)), args)
    except AdoptionError as exc:
        return _report(exc)
    except Exception as exc:  # noqa: BLE001 - a crash must not borrow a meaningful exit code
        # Exit 1 means "the work ran and the answer is no". If an unexpected fault
        # returned 1, an agent would record a verdict that was never reached.
        print(f"unexpected fault: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        _emit(
            {
                "error": NAMES[E_INTERNAL],
                "code": E_INTERNAL,
                "detail": f"{type(exc).__name__}: {exc}",
                "hint": "no claim is made about the estate; report this as a bug",
            },
            False,
        )
        return E_INTERNAL


def _report(exc: AdoptionError) -> int:
    # The error is also the single stdout document, so a caller reading only stdout
    # learns exactly why nothing happened instead of parsing an empty stream.
    _emit(exc.to_payload(), False)
    print(f"{exc.name}: {exc.detail}", file=sys.stderr)
    if exc.hint:
        print(f"hint: {exc.hint}", file=sys.stderr)
    return exc.code


if __name__ == "__main__":
    sys.exit(main())
