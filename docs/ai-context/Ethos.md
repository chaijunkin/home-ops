---
description: Documentation philosophy, hard rules, and values for the AI context
tags: ["Philosophy", "Documentation", "Ethos", "Principles"]
audience: ["LLMs", "Humans"]
categories: ["Meta[100%]", "Guidance[95%]"]
---

# Ethos: Documentation Philosophy and Principles

**Purpose**: The values, principles, and rules that guide what we capture in this knowledge base.

**Audience**: AI agents and humans contributing to repository documentation.

---

## The Philosophy

This knowledge base exists to answer: **"How does this Proxmox/Talos homelab infrastructure work as a coherent whole?"**

Not "how do I use kubectl?" or "what's the Helm chart syntax?" - those belong in external docs. This is the **context layer** that explains why the system is designed this way, how components relate, and what invariants must be preserved.

**After 10-15 minutes reading**, you should understand:

1. **What it does** - GitOps-managed Kubernetes cluster on Proxmox
2. **How it does it** - Taskfile + SOPS + Flux + Talos
3. **What must stay true** - Invariants and constraints
4. **How to find more** - Pointers to specific manifests and configs

**This is not classical documentation.** Classical docs explain how to use a tool. This explains how tools work together to manage infrastructure declaratively.

---

## The Hard Rules (Never Violate)

These are non-negotiable. Violating them undermines the entire knowledge base.

### Rule 1: Only Record What You Can Verify

**Why**: Wrong information is worse than missing information.

**Hierarchy of evidence** (prefer higher levels):
1. **Code** - Directly observed in manifests, Taskfile, scripts
2. **Documentation** - Stated in existing docs or READMEs
3. **Synthesis** - Derived from multiple verified sources
4. **User** - Confirmed by the operator

### Rule 2: When in Doubt, Omit

**Why**: Missing information prompts questions. Wrong information causes failed deployments and wasted debugging.

Better to say "see the HelmRelease for details" than guess incorrectly.

### Rule 3: Never Use Actual Domain Names or Secrets

**Why**: This is a public repository. Actual values leak information and create security exposure.

**Always use placeholders**:
- `${SECRET_DOMAIN}` - The primary domain (in hostnames, URLs, DNS records)
- `<REDACTED>` - When showing example values in documentation

**The test**: Grep for known secrets should return zero results in docs.

---

## Strong Guidance (Follow Unless You Have Good Reason)

These patterns create durable, useful documentation. Deviation should be intentional and justified.

### Capture Temporally Stable Information

**Prefer documenting**:
- Architectural patterns (GitOps, Flux reconciliation, Talos immutability)
- Infrastructure constraints (SOPS encryption, storage requirements)
- Operational invariants (never edit generated files)

**Avoid documenting**:
- Specific versions ("Flux 2.3.0") - unless they create understanding
- Configuration values (belong in manifests)

### Focus on Why, Not Just What

**Good**: "Secrets use SOPS because the repo is public and values must not be committed in plain-text"

**Bad**: "Run task sops:encrypt"

**Why**: The "why" teaches the principle. The "what" becomes obvious once you understand why.

### Provide Trails, Not Destinations

**Good**: "For app deployment patterns, see kubernetes/apps/media/plex/ks.yaml"

**Bad**: Duplicating the entire ks.yaml section here

**Why**: This knowledge base points to specific locations; it doesn't replace reading the actual configs.
