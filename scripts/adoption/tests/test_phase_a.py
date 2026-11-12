#!/usr/bin/env python3
"""Phase A acceptance tests: compile, digest stability, inspection, admission.

Run with:

    python3 scripts/adoption/tests/test_phase_a.py

Each test builds a throwaway git repository in a temp directory. Unit discovery
reads tracked files from `git ls-tree`, and several criteria need inputs that must
never exist in the real estate — a hand-edited plan, a Definition naming a unit
that is not installed. Nothing here writes inside the repository under test except
the single `TestRealEstate` case, which only reads and compares.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "engine")
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ENGINE)

import cli  # noqa: E402
from canonical import KIND_PLAN, digest  # noqa: E402
from diffing import diff, pointers  # noqa: E402
import hygiene  # noqa: E402

SLOTS = """\
apiVersion: home-ops.chaijunkin.com/slots/v1
kind: SlotLibrary
metadata:
  name: test-slots
slots:
  - name: inventory
    summary: unit resolved
    node: discover
    evidence: unit-resolved
  - name: readme
    summary: readme present
    node: render
    evidence: readme-h1-present
    requires: [inventory]
  - name: digest-pinned
    summary: images carry digests
    node: verify
    evidence: images-digest-pinned
    requires: [inventory]
  - name: proposal
    summary: pull request opened
    node: propose
    evidence: pr-opened
    requires: [inventory, readme, digest-pinned]
"""

ENV_PROPOSED = """\
apiVersion: home-ops.chaijunkin.com/environment/v1
kind: AdoptionEnvironment
metadata:
  name: pr-only
lane: proposed
authority:
  clusterWrites: none
  git: branch-and-pr
credentialRefs:
  - github-app-installation
"""

ENV_STATIC = """\
apiVersion: home-ops.chaijunkin.com/environment/v1
kind: AdoptionEnvironment
metadata:
  name: static-review
lane: static
authority:
  clusterWrites: none
  git: none
credentialRefs: []
"""

ALPHA_SLOTS = "[inventory, readme]"
BETA_SLOTS = "[inventory, digest-pinned, proposal]"
ABSENT_HASH = "ab" * 32


def git(root: str, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def write(root: str, rel: str, text: str) -> None:
    full = os.path.join(root, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(text)


def read(root: str, rel: str) -> str:
    with open(os.path.join(root, rel), encoding="utf-8") as handle:
        return handle.read()


def make_repo(
    *,
    order: tuple[str, ...] = ("alpha", "beta"),
    install: tuple[str, ...] = ("alpha", "beta"),
    env: str = "pr-only",
) -> str:
    """A minimal but real git repo: ks.yaml units plus authored adoption inputs.

    `order` controls how outputs are listed in the Definition, `install` controls
    which units actually exist. A unit named by the Definition but absent from
    `install` is how the unknown-unit path is exercised.
    """
    root = tempfile.mkdtemp(prefix="adoption-test-")
    for index, name in enumerate(install):
        unit = f"kubernetes/apps/ai/{name}"
        depends = f"\n  dependsOn:\n    - name: {install[index - 1]}" if index else ""
        write(
            root,
            f"{unit}/ks.yaml",
            f"""\
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: {name}
  namespace: flux-system
spec:
  path: ./{unit}/app{depends}
""",
        )
        write(
            root,
            f"{unit}/helmrelease.yaml",
            f"""\
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: {name}
spec:
  chart:
    spec:
      chart: app-template
      version: 3.4.0
      source:
        name: charts
  values:
    image:
      image: ghcr.io/example/{name}
      tag: 1.0.0@sha256:{ABSENT_HASH}
""",
        )

    slots = {"alpha": ALPHA_SLOTS, "beta": BETA_SLOTS}
    outputs = "".join(
        f"  - name: {name}-adopt\n    unit: kubernetes/apps/ai/{name}\n    slots: {slots[name]}\n"
        for name in order
    )
    write(
        root,
        "adoption/definitions/test/adoption.yaml",
        f"""\
apiVersion: home-ops.chaijunkin.com/adoption/v1
kind: AdoptionDefinition
metadata:
  name: test-adoption
catalog:
  base: ../../catalogs/test
environment: ../../environments/{env}.yaml
slots: library
outputs:
{outputs}""",
    )
    write(root, "adoption/slots.yaml", SLOTS)
    write(root, "adoption/environments/pr-only.yaml", ENV_PROPOSED)
    write(root, "adoption/environments/static-review.yaml", ENV_STATIC)
    write(
        root,
        "adoption/catalogs/test/registry.yaml",
        "apiVersion: home-ops.chaijunkin.com/catalog/v1\n"
        "kind: CatalogRegistry\nmetadata:\n  owner: test\ndescription: fixture\nunits:\n"
        + "".join(f"  - unit: kubernetes/apps/ai/{name}\n    tags: [t]\n" for name in order),
    )
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "test")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "fixture")
    return root


def invoke(root: str, *argv: str) -> tuple[int, str, str]:
    """Return (exit, stdout, stderr) with no assumption about stdout's format."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(["--root", root, *argv])
    return code, out.getvalue(), err.getvalue()


def yamlio_read(root: str, rel: str) -> dict:
    import yamlio

    return yamlio.read_yaml(rel, cwd=root)


class Runner(unittest.TestCase):
    def setUp(self):
        self.roots: list[str] = []

    def tearDown(self):
        for root in self.roots:
            shutil.rmtree(root, ignore_errors=True)

    def repo(self, **kwargs) -> str:
        root = make_repo(**kwargs)
        self.roots.append(root)
        return root

    def invoke(self, root: str, *argv: str) -> tuple[int, str, str]:
        return invoke(root, *argv)

    def run_cli(self, root: str, *argv: str) -> tuple[int, dict, str]:
        """JSON verbs: stdout must be exactly one JSON document."""
        code, text, err = self.invoke(root, *argv)
        stripped = text.strip()
        if not stripped:
            self.fail(f"stdout was empty (exit {code}); stderr: {err[:400]}")
        try:
            payload = json.loads(stripped)
        except ValueError as exc:
            self.fail(f"stdout was not one JSON document: {exc}\n{text[:400]}")
        remainder = stripped[len(json.dumps(payload, separators=(",", ":"))):]
        self.assertEqual(remainder.strip(), "", f"stdout carried trailing content: {remainder[:200]}")
        return code, payload, err

    def plan_of(self, root: str, *argv: str) -> tuple[int, dict, dict]:
        """Run `plan` and return (exit, summary, full plan body read back from disk)."""
        code, summary, _ = self.run_cli(root, "plan", *argv)
        if code != 0:
            return code, summary, {}
        return code, summary, json.loads(read(root, summary["path"]))


class TestMachineContract(Runner):
    def test_stdout_is_exactly_one_json_document(self):
        code, text, _ = self.invoke(self.repo(), "plan")
        self.assertEqual(code, 0)
        decoder = json.JSONDecoder()
        value, end = decoder.raw_decode(text.strip())
        self.assertEqual(text.strip()[end:].strip(), "", "stdout carried a second value")
        self.assertIsInstance(value, dict)

    def test_logs_never_share_stdout_with_the_document(self):
        root = self.repo()
        code, text, err = self.invoke(root, "catalog", "pin")
        self.assertEqual(code, 0)
        self.assertEqual(text.count("\n"), 1, "canonical output is one line plus its terminator")
        self.assertEqual(text, text.strip() + "\n")
        json.loads(text)
        self.assertNotIn("written", err, "the document's own content leaked into stderr")

    def test_exit_codes_are_documented_and_banded(self):
        import errors

        for code, name in errors.NAMES.items():
            self.assertTrue(name.startswith("E-") or name == "OK", name)
            self.assertIn(code, errors.MEANINGS)
            if code > 3:
                self.assertTrue(
                    10 <= code <= 19 or 20 <= code <= 31 or 40 <= code <= 50,
                    f"code {code} falls outside every published band",
                )

    def test_a_fault_never_borrows_a_meaningful_exit_code(self):
        """Exit 1 means "the work ran and the answer is no", so a crash may not use it."""
        import errors

        def explode(*_args, **_kwargs):
            raise RuntimeError("simulated engine fault")

        root = self.repo()
        original = cli.Context.plan
        cli.Context.plan = explode
        try:
            code, payload, _ = self.run_cli(root, "plan")
        finally:
            cli.Context.plan = original
        self.assertEqual(code, errors.E_INTERNAL)
        self.assertEqual(payload["error"], "E-INTERNAL")


class TestStaticHygiene(unittest.TestCase):
    """Guards the defect class that hid a crash handler which could not run."""

    def test_engine_sources_have_no_undefined_or_unused_names(self):
        problems = hygiene.check_paths([ENGINE, os.path.join(os.path.dirname(ENGINE), "adoption.py")])
        self.assertEqual(problems, [], "static hygiene: " + "; ".join(problems))


class TestCompile(Runner):
    def test_compiles_and_reports_counts(self):
        code, summary, body = self.plan_of(self.repo())
        self.assertEqual(code, 0)
        self.assertEqual(summary["outputs"], 2)
        self.assertEqual(summary["nodes"], 5)
        self.assertEqual(body["schemaVersion"], KIND_PLAN)

    def test_two_compiles_are_byte_identical(self):
        root = self.repo()
        first_path = self.run_cli(root, "plan")[1]["path"]
        first = read(root, first_path)
        second_path = self.run_cli(root, "plan")[1]["path"]
        self.assertEqual(first, read(root, second_path))
        self.assertEqual(first_path, second_path, "the digest moved between identical compiles")

    def test_authoring_order_does_not_change_desired_state_identity(self):
        a = self.plan_of(self.repo(order=("alpha", "beta")))[2]["desiredStateDigest"]
        b = self.plan_of(self.repo(order=("beta", "alpha")))[2]["desiredStateDigest"]
        self.assertEqual(a, b, "listing outputs in another order looked like a different plan")

    def test_plan_declares_itself_description_only(self):
        body = self.plan_of(self.repo())[2]
        self.assertEqual(body["authority"], "description-only")
        self.assertEqual(body["lane"], "proposed")

    def test_transport_locators_are_not_desired_state(self):
        """A credential rotation must not invalidate an adoption claim."""
        body = self.plan_of(self.repo())[2]
        state = json.dumps(body["desiredState"])
        self.assertNotIn("credentialRefs", state)
        self.assertNotIn("github-app-installation", state)
        self.assertTrue(body["environmentDigest"].startswith("sha256:"))

    def test_plan_digest_covers_everything_but_itself(self):
        body = self.plan_of(self.repo())[2]
        stripped = {k: v for k, v in body.items() if k != "planDigest"}
        self.assertEqual(digest(KIND_PLAN, stripped), body["planDigest"])

    def test_changing_a_slot_definition_changes_identity(self):
        root = self.repo()
        before = self.plan_of(root)[2]["desiredStateDigest"]
        write(root, "adoption/slots.yaml", SLOTS.replace("readme-h1-present", "readme-h2-present"))
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "evidence rename")
        after = self.plan_of(root)[2]["desiredStateDigest"]
        self.assertNotEqual(before, after)


class TestGraph(Runner):
    def test_flux_dependsOn_becomes_a_cross_unit_edge(self):
        """beta waits on alpha because beta's ks.yaml says so, not because it was authored."""
        body = self.plan_of(self.repo())[2]
        edges = {(e["from"], e["to"]) for e in body["edges"]}
        self.assertIn(("beta-adopt/digest-pinned", "alpha-adopt/inventory"), edges)
        self.assertIn(("beta-adopt/proposal", "alpha-adopt/inventory"), edges)
        self.assertNotIn(("alpha-adopt/readme", "beta-adopt/inventory"), edges)

    def test_order_respects_every_edge(self):
        body = self.plan_of(self.repo())[2]
        position = {node: index for index, node in enumerate(body["order"])}
        for edge in body["edges"]:
            self.assertLess(position[edge["to"]], position[edge["from"]], edge)

    def test_order_is_reproducible(self):
        self.assertEqual(self.plan_of(self.repo())[2]["order"], self.plan_of(self.repo())[2]["order"])

    def test_order_contains_every_node(self):
        body = self.plan_of(self.repo())[2]
        self.assertEqual(sorted(body["order"]), sorted(n["id"] for n in body["nodes"]))

    def test_cycle_in_slot_requires_is_reported_not_hung(self):
        """proposal needs digest-pinned and digest-pinned needs proposal: no order exists."""
        import errors

        root = self.repo()
        write(root, "adoption/slots.yaml",
              SLOTS.replace("    evidence: images-digest-pinned\n    requires: [inventory]",
                            "    evidence: images-digest-pinned\n    requires: [inventory, proposal]"))
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "cycle")
        code, payload, _ = self.run_cli(root, "plan")
        self.assertEqual(code, errors.E_GRAPH_CYCLE)
        self.assertEqual(payload["error"], "E-GRAPH-CYCLE")
        self.assertIn("proposal", payload["detail"])

    def test_mermaid_and_dot_render_as_text_on_stdout(self):
        """The one documented exception: a requested diagram format is the product."""
        root = self.repo()
        code, mermaid, _ = self.invoke(root, "graph", "--format", "mermaid")
        self.assertEqual(code, 0)
        self.assertIn("flowchart TD", mermaid)
        self.assertIn("alpha-adopt", mermaid)
        self.assertIn("inventory", mermaid)
        self.assertIn("-->", mermaid)

        code, dot, _ = self.invoke(root, "graph", "--format", "dot")
        self.assertEqual(code, 0)
        self.assertIn("digraph adoption", dot)
        self.assertIn('"beta-adopt/proposal"', dot, "dot addresses nodes by their plan id")

    def test_graph_scopes_to_one_named_output(self):
        root = self.repo()
        code, _, _ = self.invoke(root, "graph", "--format", "json", "--output", "alpha-adopt")
        self.assertEqual(code, 0)

    def test_graph_json_view_keeps_only_scoped_edges(self):
        root = self.repo()
        code, text, _ = self.invoke(root, "graph", "--format", "json", "--output", "alpha-adopt")
        self.assertEqual(code, 0)
        body = json.loads(text)
        self.assertEqual({node["output"] for node in body["nodes"]}, {"alpha-adopt"})
        self.assertTrue(body["edges"], "scoping dropped every edge")
        for edge in body["edges"]:
            self.assertTrue(edge["from"].startswith("alpha-adopt/"))
            self.assertTrue(edge["to"].startswith("alpha-adopt/"))

    def test_unknown_format_is_a_usage_error(self):
        code, payload, _ = self.run_cli(self.repo(), "graph", "--format", "graphviz")
        self.assertEqual(code, 2)


class TestCheckDetectsDrift(Runner):
    def test_check_passes_when_committed(self):
        root = self.repo()
        self.run_cli(root, "plan")
        code, payload, _ = self.run_cli(root, "plan", "--check")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "current")

    def test_check_fails_when_inputs_change(self):
        root = self.repo()
        self.run_cli(root, "plan")
        write(root, "adoption/definitions/test/adoption.yaml",
              read(root, "adoption/definitions/test/adoption.yaml").replace("test-adoption", "test-adoption-2"))
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "definition renamed")
        code, payload, _ = self.run_cli(root, "plan", "--check")
        self.assertEqual(code, 3)
        self.assertEqual(payload["error"], "E-DIFF")

    def test_hand_editing_a_plan_breaks_name_content_agreement(self):
        """A generated plan is addressed by the digest of its own bytes."""
        root = self.repo()
        rel = self.run_cli(root, "plan")[1]["path"]
        body = json.loads(read(root, rel))
        body["nodes"][0]["evidence"] = "tampered"
        write(root, rel, json.dumps(body))
        code, payload, _ = self.run_cli(root, "plan", "--check")
        self.assertEqual(code, 3)
        self.assertIn("hash", payload["detail"])

    def test_truncating_a_plan_is_detected(self):
        root = self.repo()
        rel = self.run_cli(root, "plan")[1]["path"]
        write(root, rel, read(root, rel)[:200])
        code, payload, _ = self.run_cli(root, "plan", "--check")
        self.assertEqual(code, 3)

    def test_missing_plan_is_a_diff_not_a_success(self):
        root = self.repo()
        code, payload, _ = self.run_cli(root, "plan", "--check")
        self.assertEqual(code, 3)
        self.assertIn("missing", payload["detail"])


class TestDiff(Runner):
    def test_name_selectors_hide_reindexing(self):
        before = {"outputs": [{"name": "a", "slots": ["inventory"]}, {"name": "b", "slots": ["inventory"]}]}
        after = {"outputs": [
            {"name": "a", "slots": ["inventory"]},
            {"name": "new", "slots": ["inventory"]},
            {"name": "b", "slots": ["inventory", "readme"]},
        ]}
        result = diff(before, after)
        self.assertFalse(result["identical"])
        self.assertEqual([item["pointer"] for item in result["changed"]], [])
        self.assertEqual(
            [item["pointer"] for item in result["added"]],
            ["/outputs/@name=b/slots/1", "/outputs/@name=new/name", "/outputs/@name=new/slots/0"],
        )
        self.assertEqual(result["removed"], [])
        for item in result["added"] + result["removed"] + result["changed"]:
            self.assertNotIn("/outputs/1", item["pointer"], "an output was addressed by position")
            self.assertNotIn("/outputs/2", item["pointer"], "an output was addressed by position")

    def test_positional_arrays_still_use_indexes(self):
        self.assertEqual(sorted(pointers({"order": ["a", "b"]})), ["/order/0", "/order/1"])

    def test_digest_fields_are_volatile_by_default(self):
        before = {"planDigest": "sha256:1", "lane": "static"}
        after = {"planDigest": "sha256:2", "lane": "static"}
        self.assertTrue(diff(before, after)["identical"])
        self.assertFalse(diff(before, after, include_volatile=True)["identical"])

    def test_identical_plans_diff_clean(self):
        root = self.repo()
        rel = self.run_cli(root, "plan")[1]["path"]
        shutil.copy(os.path.join(root, rel), os.path.join(root, "a.json"))
        self.run_cli(root, "plan")
        shutil.copy(os.path.join(root, rel), os.path.join(root, "b.json"))
        code, payload, _ = self.run_cli(root, "diff", "--before", "a.json", "--after", "b.json")
        self.assertEqual(code, 0)
        self.assertTrue(payload["identical"])

    def test_one_slot_edit_touches_one_output(self):
        root = self.repo()
        first = self.run_cli(root, "plan")[1]["path"]
        shutil.copy(os.path.join(root, first), os.path.join(root, "a.json"))
        path = "adoption/definitions/test/adoption.yaml"
        write(root, path, read(root, path).replace(ALPHA_SLOTS, "[inventory]"))
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "drop readme")
        second = self.run_cli(root, "plan")[1]["path"]
        shutil.copy(os.path.join(root, second), os.path.join(root, "b.json"))
        code, payload, _ = self.run_cli(root, "diff", "--before", "a.json", "--after", "b.json")
        self.assertEqual(code, 3)
        scoped = [
            item["pointer"]
            for item in payload["added"] + payload["removed"] + payload["changed"]
            if item["pointer"].split("/")[1] in ("nodes", "edges", "outputs")
        ]
        self.assertTrue(scoped, "no structural change was reported")
        for pointer in scoped:
            self.assertIn("alpha-adopt", pointer, f"change leaked elsewhere: {pointer}")
        # `order` is a sequence by definition, so its pointers are positional and a
        # removal shifts later entries — and a shifted entry's *value* can name
        # another output. That is not an output looking replaced, so the claim here
        # is scoped to structural records, which are addressed by name.
        structural_items = [
            item
            for item in payload["added"] + payload["removed"]
            if not item["pointer"].startswith("/order/")
        ]
        self.assertNotIn(
            "beta-adopt",
            json.dumps(structural_items),
            "an untouched output appeared in the diff",
        )

    def test_superseded_plans_are_pruned_so_only_the_current_one_remains(self):
        root = self.repo()
        self.run_cli(root, "plan")
        path = "adoption/definitions/test/adoption.yaml"
        write(root, path, read(root, path).replace("test-adoption", "test-adoption-v2"))
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "rename")
        summary = self.run_cli(root, "plan")[1]
        self.assertEqual(summary["prunedSuperseded"], 1)
        plans = os.listdir(os.path.join(root, ".adoption/plans"))
        self.assertEqual(plans, [os.path.basename(summary["path"])])

    def test_pointers_escape_reserved_characters(self):
        self.assertEqual(sorted(pointers({"a/b": {"c~d": 1}})), ["/a~1b/c~0d"])


class TestAdmission(Runner):
    def test_unknown_unit_fails_before_any_plan_is_written(self):
        root = self.repo(install=("alpha",))
        code, payload, _ = self.run_cli(root, "plan")
        self.assertEqual(code, 13)
        self.assertEqual(payload["error"], "E-UNIT-UNKNOWN")
        self.assertIn("beta", payload["detail"])
        self.assertFalse(os.path.exists(os.path.join(root, ".adoption/plans")))

    def test_unknown_slot_is_named_with_candidates(self):
        root = self.repo()
        write(root, "adoption/definitions/test/adoption.yaml",
              read(root, "adoption/definitions/test/adoption.yaml").replace(ALPHA_SLOTS, "[inventory, readmez]"))
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "typo")
        code, payload, _ = self.run_cli(root, "plan")
        self.assertEqual(code, 14)
        self.assertIn("readmez", payload["detail"])
        self.assertIn("readme", payload["hint"])

    def test_lane_ceiling_blocks_a_propose_node(self):
        root = self.repo(env="static-review")
        code, payload, _ = self.run_cli(root, "plan")
        self.assertEqual(code, 19)
        self.assertEqual(payload["error"], "E-LANE-VIOLATION")
        self.assertIn("proposal", payload["detail"])

    def test_unknown_field_is_rejected_with_accepted_names(self):
        root = self.repo()
        write(root, "adoption/definitions/test/adoption.yaml",
              read(root, "adoption/definitions/test/adoption.yaml").replace("environment:", "enviroment:", 1))
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "typo")
        code, payload, _ = self.run_cli(root, "plan")
        self.assertEqual(code, 12)
        self.assertIn("unknown field", payload["detail"])
        self.assertIn("environment", payload["hint"])

    def test_cluster_writes_cannot_be_requested(self):
        root = self.repo()
        write(root, "adoption/environments/pr-only.yaml",
              read(root, "adoption/environments/pr-only.yaml").replace("clusterWrites: none", "clusterWrites: all"))
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "authority grab")
        code, payload, _ = self.run_cli(root, "plan")
        self.assertEqual(code, 12)
        self.assertIn("none", payload["detail"])

    def test_digest_in_registry_is_rejected(self):
        root = self.repo()
        write(root, "adoption/catalogs/test/registry.yaml",
              read(root, "adoption/catalogs/test/registry.yaml").replace(
                  "units:\n",
                  "units:\n  - unit: ghcr.io/example/thing@sha256:" + "cd" * 32 + "\n    tags: [t]\n",
              ))
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "digest in registry")
        code, payload, _ = self.run_cli(root, "catalog", "show")
        self.assertEqual(code, 16)
        self.assertEqual(payload["error"], "E-REGISTRY-DIGEST")

    def test_missing_definition_is_named_with_a_path(self):
        root = self.repo()
        code, payload, _ = self.run_cli(root, "plan", "--definition", "adoption/definitions/nope/x.yaml")
        self.assertEqual(code, 10)
        self.assertIn("nope", payload["detail"])


class TestLock(Runner):
    def test_pin_then_check_is_current(self):
        root = self.repo()
        code, payload, _ = self.run_cli(root, "catalog", "pin")
        self.assertEqual(code, 0)
        self.assertEqual(payload["members"], 2)
        code, payload, _ = self.run_cli(root, "catalog", "pin", "--check")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "current")

    def test_shared_chart_becomes_a_derived_set(self):
        root = self.repo()
        self.run_cli(root, "catalog", "pin")
        body = self.lock_body(root)
        self.assertEqual({pin["pinnedBy"] for pin in body["pins"]}, {"platform"})
        self.assertTrue(all("derivedFrom" in pin for pin in body["pins"]))

    def test_a_lone_chart_is_pinned_by_its_unit(self):
        root = self.repo()
        other = read(root, "kubernetes/apps/ai/beta/helmrelease.yaml").replace("version: 3.4.0", "version: 4.0.0")
        write(root, "kubernetes/apps/ai/beta/helmrelease.yaml", other)
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "beta alone")
        self.run_cli(root, "catalog", "pin")
        by_unit = {pin["unit"]: pin["pinnedBy"] for pin in self.lock_body(root)["pins"]}
        self.assertEqual(by_unit["kubernetes/apps/ai/beta"], "unit")

    def test_lock_names_the_registry_bytes_it_pins(self):
        root = self.repo()
        self.run_cli(root, "catalog", "pin")
        registry_digest = self.run_cli(root, "catalog", "show")[1]["registryDigest"]
        self.assertEqual(self.lock_body(root)["registryDigest"], registry_digest)

    def test_registry_change_stales_the_lock_and_repair_is_possible(self):
        """The repair command must not be blocked by the check that fires on staleness."""
        root = self.repo()
        self.run_cli(root, "catalog", "pin")
        write(root, "adoption/catalogs/test/registry.yaml",
              read(root, "adoption/catalogs/test/registry.yaml") + "  - unit: kubernetes/apps/ai/alpha\n    tags: [t]\n")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "registry moved")

        code, payload, _ = self.run_cli(root, "plan")
        self.assertEqual(code, 17, "a plan must not compile on pins from another registry")
        self.assertEqual(payload["error"], "E-LOCK-STALE")

        code, payload, _ = self.run_cli(root, "catalog", "pin", "--check")
        self.assertEqual(code, 3, "the check should report drift, not refuse to look")

        code, _, _ = self.run_cli(root, "catalog", "pin")
        self.assertEqual(code, 0, "regenerating a stale lock is the documented repair")
        code, _, _ = self.run_cli(root, "plan")
        self.assertEqual(code, 0, "the plan should compile once the lock is repaired")

    def test_bump_check_reports_no_drift_when_lock_is_fresh(self):
        root = self.repo()
        self.run_cli(root, "catalog", "pin")
        code, payload, _ = self.run_cli(root, "catalog", "bump")
        self.assertEqual(code, 0)
        self.assertEqual(payload["count"], 0)

    def test_bump_check_finds_manifest_drift(self):
        root = self.repo()
        self.run_cli(root, "catalog", "pin")
        write(root, "kubernetes/apps/ai/alpha/helmrelease.yaml",
              read(root, "kubernetes/apps/ai/alpha/helmrelease.yaml").replace("version: 3.4.0", "version: 3.9.0"))
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "chart moved")
        code, payload, _ = self.run_cli(root, "catalog", "bump")
        self.assertEqual(code, 3)
        self.assertEqual(payload["drifted"], ["kubernetes/apps/ai/alpha"])

    def test_concurrent_lock_write_is_refused(self):
        """Compare-and-swap: a lock that moved underneath the caller is never overwritten."""
        from errors import AdoptionError
        from inputs import write_lock

        root = self.repo()
        rel = "adoption/catalogs/test/pins.lock.yaml"
        write_lock(rel, "schemaVersion: adoption.lock/v1\n", root, expect=None)
        write(root, rel, "schemaVersion: adoption.lock/v1\n# someone else won\n")
        with self.assertRaises(AdoptionError) as caught:
            write_lock(rel, "schemaVersion: adoption.lock/v1\n# ours\n", root, expect=None)
        self.assertEqual(caught.exception.code, 17)
        self.assertIn("# someone else won", read(root, rel), "the other writer was clobbered")

    def lock_body(self, root: str) -> dict:
        import yamlio

        return yamlio.read_yaml("adoption/catalogs/test/pins.lock.yaml", cwd=root)


class TestNoClusterWritePath(Runner):
    """Phase B's strongest guarantee, asserted now so it cannot arrive by accident."""

    FORBIDDEN = (
        "kubectl",
        "helm upgrade",
        "helm install",
        "flux apply",
        "flux bootstrap",
        "talosctl apply",
        "server-side",
    )

    def test_engine_sources_contain_no_cluster_mutation_call(self):
        for name in sorted(os.listdir(ENGINE)):
            if not name.endswith(".py"):
                continue
            text = open(os.path.join(ENGINE, name), encoding="utf-8").read().lower()
            for needle in self.FORBIDDEN:
                self.assertNotIn(needle, text, f"{name} mentions {needle!r}")

    def test_reading_the_fleet_never_modifies_it(self):
        """`plan` may write its own output; nothing may touch anything else."""
        root = self.repo()
        self.invoke(root, "plan")
        baseline = git_status(root)
        self.invoke(root, "graph", "--format", "dot")
        self.invoke(root, "catalog", "show")
        self.assertEqual(git_status(root), baseline, "a read-only verb changed the tree")
        for line in baseline.splitlines():
            self.assertIn(".adoption/", line, f"a verb wrote outside plan output: {line}")

    def test_compiling_does_not_touch_kubernetes_directories(self):
        root = self.repo()
        self.invoke(root, "plan")
        self.invoke(root, "catalog", "pin")
        changed = [line for line in git_status(root).splitlines() if "kubernetes/" in line]
        self.assertEqual(changed, [])


def git_status(root: str) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True
    ).stdout


class TestRealEstate(unittest.TestCase):
    """The Definition committed in home-ops must compile, stay stable, and check clean."""

    def test_agent_blueprint_definition_compiles_and_checks(self):
        code, text, err = self.invoke_plan("--check")
        self.assertEqual(code, 0, f"plan --check exited {code}: {text} {err}")

    def test_compiled_plan_is_reachable_and_its_graph_is_ordered(self):
        code, text, _ = self.invoke_plan()
        self.assertEqual(code, 0)
        summary = json.loads(text)
        self.assertGreaterEqual(summary["outputs"], 5)
        self.assertGreaterEqual(summary["edges"], 1)

    def invoke_plan(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["--root", REPO_ROOT, "plan", *argv])
        return code, out.getvalue(), err.getvalue()


class TestChartResolution(unittest.TestCase):
    """Chart resolution against the shape this estate actually has.

    161 HelmReleases use `spec.chartRef: {kind: OCIRepository, name: …}` and none
    inline `spec.chart.spec`, so resolution is a join against OCIRepository objects
    that live outside the unit. Every OCIRepository in this estate selects a tag and
    none selects a digest, which the lock has to disclose instead of implying.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="adoption-resolve-")
        self.roots = [self.root]

    def tearDown(self):
        for root in self.roots:
            shutil.rmtree(root, ignore_errors=True)

    def write(self, rel: str, text: str) -> None:
        write(self.root, rel, text)

    def commit(self) -> None:
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.invalid")
        git(self.root, "config", "user.name", "t")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "fixture")

    def helmrelease(self, unit: str, name: str) -> None:
        write(self.root, f"kubernetes/apps/{unit}/helmrelease.yaml", f"""\
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: {name}
spec:
  chartRef:
    kind: OCIRepository
    name: {name}-source
""")

    def source(self, rel: str, name: str, url: str, *, tag: str = "", digest: str = "") -> None:
        ref = f"    digest: {digest}\n" if digest else f"    tag: {tag}\n"
        write(self.root, rel, f"""\
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: OCIRepository
metadata:
  name: {name}
spec:
  url: {url}
  ref:
{ref}""")

    def pins(self, unit: str) -> dict:
        import repo

        return repo.unit_pins(self.root, unit)

    def test_chart_ref_resolves_through_an_out_of_unit_source(self):
        self.helmrelease("ai/alpha", "alpha")
        self.source("kubernetes/components/common/alpha/ocirepository.yaml", "alpha-source",
                    "oci://ghcr.io/example/charts/alpha", tag="1.2.3")
        self.commit()
        charts = self.pins("kubernetes/apps/ai/alpha")["charts"]
        self.assertEqual([c["chartRef"] for c in charts], ["OCIRepository/alpha-source"])
        self.assertEqual(charts[0]["resolved"], "oci://ghcr.io/example/charts/alpha@1.2.3")
        self.assertEqual(charts[0]["resolutionKind"], "tag")

    def test_digest_source_is_reported_as_a_real_pin(self):
        self.helmrelease("ai/alpha", "alpha")
        self.source("kubernetes/components/common/alpha/ocirepository.yaml", "alpha-source",
                    "oci://ghcr.io/example/charts/alpha", digest="sha256:" + "ab" * 32)
        self.commit()
        charts = self.pins("kubernetes/apps/ai/alpha")["charts"]
        self.assertEqual(charts[0]["resolutionKind"], "digest")

    def test_a_name_defined_twice_differently_is_not_resolved(self):
        self.helmrelease("ai/alpha", "alpha")
        self.source("kubernetes/components/a/ocirepository.yaml", "alpha-source",
                    "oci://ghcr.io/example/charts/alpha", tag="1.0.0")
        self.source("kubernetes/components/b/ocirepository.yaml", "alpha-source",
                    "oci://ghcr.io/example/charts/alpha", tag="2.0.0")
        self.commit()
        charts = self.pins("kubernetes/apps/ai/alpha")["charts"]
        self.assertIsNone(charts[0]["resolved"], "an ambiguous name was reported as resolved")
        self.assertEqual(len(charts[0]["ambiguous"]), 2)
        self.assertEqual(len(charts[0]["definedIn"]), 2)

    def test_two_definitions_agreeing_on_bytes_are_one_resolution(self):
        self.helmrelease("ai/alpha", "alpha")
        for where in ("kubernetes/components/a/ocirepository.yaml", "kubernetes/components/b/ocirepository.yaml"):
            self.source(where, "alpha-source", "oci://ghcr.io/example/charts/alpha", tag="1.0.0")
        self.commit()
        charts = self.pins("kubernetes/apps/ai/alpha")["charts"]
        self.assertEqual(charts[0]["resolved"], "oci://ghcr.io/example/charts/alpha@1.0.0")
        self.assertNotIn("ambiguous", charts[0])

    def test_an_unresolvable_chart_ref_is_recorded_not_dropped(self):
        self.helmrelease("ai/alpha", "alpha")
        self.commit()
        charts = self.pins("kubernetes/apps/ai/alpha")["charts"]
        self.assertEqual(len(charts), 1, "an unresolvable reference disappeared from the lock")
        self.assertIsNone(charts[0]["resolved"])
        self.assertEqual(charts[0]["resolutionKind"], "none")

    def test_a_source_naming_no_ref_is_recorded_as_the_bare_url(self):
        """`@unresolved` would read like a copyable reference; the bare url does not."""
        self.helmrelease("ai/alpha", "alpha")
        write(self.root, "kubernetes/components/a/ocirepository.yaml", """\
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: OCIRepository
metadata:
  name: alpha-source
spec:
  url: oci://ghcr.io/example/charts/alpha
""")
        self.commit()
        charts = self.pins("kubernetes/apps/ai/alpha")["charts"]
        self.assertEqual(charts[0]["resolved"], "oci://ghcr.io/example/charts/alpha")
        self.assertEqual(charts[0]["resolutionKind"], "none")

    def test_a_non_mapping_document_does_not_abort_the_scan(self):
        """The estate tracks YAML whose root is a sequence; `.kind` on it is an error."""
        self.helmrelease("ai/alpha", "alpha")
        self.source("kubernetes/components/common/alpha/ocirepository.yaml", "alpha-source",
                    "oci://ghcr.io/example/charts/alpha", tag="1.2.3")
        write(self.root, "kubernetes/apps/other/hooks.yaml", "- id: thing\n  command: run\n")
        self.commit()
        charts = self.pins("kubernetes/apps/ai/alpha")["charts"]
        self.assertEqual(charts[0]["resolved"], "oci://ghcr.io/example/charts/alpha@1.2.3")

    def test_a_member_with_no_chart_is_not_claimed_unit_pinned(self):
        write(self.root, "kubernetes/apps/ai/beta/ks.yaml", """\
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: beta
  namespace: flux-system
spec:
  path: ./kubernetes/apps/ai/beta/app
""")
        write(self.root, "kubernetes/apps/ai/beta/helmrelease.yaml", """\
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: beta
spec:
  values:
    image:
      image: ghcr.io/example/beta
      tag: 1.0.0
""")
        write(self.root, "adoption/catalogs/test/registry.yaml", """\
apiVersion: home-ops.chaijunkin.com/catalog/v1
kind: CatalogRegistry
metadata:
  owner: test
description: fixture
units:
  - unit: kubernetes/apps/ai/beta
    tags: [t]
""")
        write(self.root, "adoption/slots.yaml", SLOTS)
        write(self.root, "adoption/environments/pr-only.yaml", ENV_PROPOSED)
        write(self.root, "adoption/definitions/test/adoption.yaml", """\
apiVersion: home-ops.chaijunkin.com/adoption/v1
kind: AdoptionDefinition
metadata:
  name: test-adoption
catalog:
  base: ../../catalogs/test
environment: ../../environments/pr-only.yaml
slots: library
outputs:
  - name: beta-adopt
    unit: kubernetes/apps/ai/beta
    slots: [inventory]
""")
        self.commit()
        code, text, _err = invoke(self.root, "catalog", "pin")
        self.assertEqual(code, 0, text)
        body = yamlio_read(self.root, "adoption/catalogs/test/pins.lock.yaml")
        self.assertEqual(body["pins"][0]["pinnedBy"], "none", "a chartless unit claimed a chart pin")
        self.assertEqual(body["pins"][0]["images"], [{"ref": "ghcr.io/example/beta:1.0.0"}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
