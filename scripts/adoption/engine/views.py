#!/usr/bin/env python3
"""Human-facing graph views: mermaid, dot, json.

Presentation is not an interface contract: only `json` is stable, and it is the
same bytes `adoption plan` writes. The two diagram formats exist so a reviewer can
see ordering with their eyes before they approve a Run.
"""

from __future__ import annotations

from canonical import pretty
from errors import E_USAGE, fail

FORMATS = ("mermaid", "dot", "json")


def render(plan: dict, fmt: str, only_output: str | None = None) -> str:
    if fmt not in FORMATS:
        fail(E_USAGE, f"--format must be one of {', '.join(FORMATS)}")
    nodes = [n for n in plan["nodes"] if only_output is None or n["output"] == only_output]
    keep = {n["id"] for n in nodes}
    edges = [e for e in plan["edges"] if e["from"] in keep and e["to"] in keep]
    if fmt == "json":
        return pretty({
            "planDigest": plan["planDigest"],
            "lane": plan["lane"],
            "nodes": nodes,
            "edges": edges,
            "order": [i for i in plan["order"] if i in keep],
        })
    if fmt == "mermaid":
        return _mermaid(plan, nodes, edges)
    return _dot(plan, nodes, edges)


def _mermaid(plan: dict, nodes: list[dict], edges: list[dict]) -> str:
    ids = {node["id"]: f"n{index}" for index, node in enumerate(sorted(nodes, key=lambda n: n["id"]))}
    lines = ["flowchart TD"]
    by_output: dict[str, list[dict]] = {}
    for node in sorted(nodes, key=lambda n: n["id"]):
        by_output.setdefault(node["output"], []).append(node)
    for output in sorted(by_output):
        unit = by_output[output][0]["unit"]
        lines.append(f'  subgraph {ids[by_output[output][0]["id"]] + "_g"}["{output} &mdash; {unit}"]')
        for node in by_output[output]:
            kind = node["kind"]
            lines.append(f'    {ids[node["id"]]}["{node["slot"]}<br/><i>{kind}</i>"]')
        lines.append("  end")
    for edge in sorted(edges, key=lambda e: (e["from"], e["to"])):
        if edge["from"] in ids and edge["to"] in ids:
            lines.append(f'  {ids[edge["from"]]} --> {ids[edge["to"]]}')
    lines.append("")
    return "\n".join(lines)


def _dot(plan: dict, nodes: list[dict], edges: list[dict]) -> str:
    lines = [
        "digraph adoption {",
        "  rankdir=LR;",
        '  node [shape=box, fontname="Helvetica", fontsize=10];',
        f'  labelloc="t"; label="plan {plan["planDigest"][:18]}…  lane={plan["lane"]}";',
    ]
    for node in sorted(nodes, key=lambda n: n["id"]):
        label = f'{node["output"]}\\n{node["slot"]} ({node["kind"]})'
        lines.append(f'  "{node["id"]}" [label="{label}"];')
    for edge in sorted(edges, key=lambda e: (e["from"], e["to"])):
        lines.append(f'  "{edge["from"]}" -> "{edge["to"]}";')
    lines.append("}")
    return "\n".join(lines) + "\n"
