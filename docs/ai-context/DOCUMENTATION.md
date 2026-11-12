---
description: Vault-repo documentation contract - where knowledge lives, what is generated, and what must never be run.
tags: ["Documentation", "Contract", "Vault", "README"]
audience: ["LLMs", "Humans"]
categories: ["Meta[100%]", "Guidance[90%]"]
---

# DOCUMENTATION: The Vault-Repo Contract

**Purpose**: Which repository owns which kind of documentation, and the generated-file landmines.

---

## Ownership

| Kind of doc | Owner | Location |
| ----------- | ----- | -------- |
| Cluster state (the truth itself) | this repo | `kubernetes/apps/**` manifests |
| AI context capsules (invariants, boundaries) | this repo | `docs/ai-context/` (format: `writing-capsules.md`, philosophy: `Ethos.md`) |
| Per-app operating notes | this repo | `kubernetes/apps/<cat>/<app>/README.md`, content sourced from `APP_KNOWLEDGE` in `scripts/sync_service_docs.py` |
| All narrative knowledge (architecture, runbooks, decisions, PRRs) | private `DefaultVault` Obsidian vault | `pages/TECH/Cloudjur/**` — golden source, never duplicated here |

The canonical strategy page lives in the vault: `DefaultVault/pages/TECH/Cloudjur/home-ops/Documentation-Strategy.md`.

## PRR pattern

Every app README links its Product Requirements/Reference page:
`https://wiki.${SECRET_DOMAIN}/pages/tech/cloudjur/<category>/<app>`

## Generated files — never hand-edit

- `docs/services-list.md` and the vault `Services-Inventory.md` page — regenerated from live-cluster routes by `scripts/sync_service_docs.py`.
- Per-app README managed regions — change `APP_KNOWLEDGE`, then re-sync.

**Landmine**: `scripts/generate_readmes.py` unconditionally overwrites every per-app README. It is legacy. Never run it; use `sync_service_docs.py`.

## Workflow

1. Edit generator inputs (`APP_KNOWLEDGE`) or vault pages — not outputs.
2. `task repository:sync-docs` then `task repository:check-docs` (drift gate must exit 0 before PR).
3. Public-repo rule: `${SECRET_DOMAIN}` / `<REDACTED>` placeholders only (Ethos Rule 3); deep explanations belong in the vault, not inline prose.
