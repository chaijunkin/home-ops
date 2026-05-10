---
description: Collaborative planning lifecycle for AI-assisted work across homelab infrastructure
tags: ["Planning", "RiskAssessment", "IncidentResponse", "Collaboration"]
audience: ["LLMs", "Humans"]
categories: ["Workflows[100%]", "Philosophy[70%]"]
---

# Collaborative Planning Lifecycle

Structured collaboration between human and AI produces better outcomes than ad-hoc requests. This document captures the lifecycle: **Idea → Planning → Risk Assessment → Execution → Incident Response**.

---

## Philosophy

**Why structure matters**: Complex changes benefit from exploration before action. Rushing to implementation risks missing dependencies, breaking existing functionality, or solving the wrong problem.

**Lightweight, not bureaucratic**: These phases are mental checkpoints, not formal gates. A simple change might flow through all five in minutes. A complex migration might spend hours in planning.

---

## The Five Phases

```
Idea → Planning → Risk Assessment → Execution → Incident Response
  │        │              │              │              │
  │        │              │              │              └─ Learn from failures
  │        │              │              └─ Small steps, verify each
  │        │              └─ What could go wrong?
  │        └─ Explore before proposing
  └─ Problem + outcome, not solution
```

| Phase     | Focus      | Key Question                                  |
| --------- | ---------- | --------------------------------------------- |
| Idea      | Intent     | What problem are we solving?                  |
| Planning  | Discovery  | What exists? What patterns?                   |
| Risk      | Prevention | What could go wrong? What's the blast radius? |
| Execution | Progress   | Did each step succeed? Can we verify?         |
| Incident  | Learning   | What happened? What did we learn?             |

---

## Phase Capsules

### Capsule: ExplorationFirst

**Invariant**
Understand the codebase before proposing changes; use tools to discover what exists.

**Example**
```
Grep for similar apps → read existing HelmReleases → identify patterns → propose approach
```
//BOUNDARY: Never propose changes to code you haven't read.

**Depth**
- Techniques: Grep, Glob, Read existing manifests in `kubernetes/apps/`
- Trade-off: Time exploring vs missing critical dependencies
- NotThis: Proposing solutions based on assumptions

---

### Capsule: RiskDiscovery

**Invariant**
Ask "what could go wrong?" during planning; identify blast radius and dependencies.

**Example**
Before changing a shared component:
1. What uses this? (grep across kubernetes/apps/)
2. What breaks if this fails? (blast radius)
3. What's the rollback? (revert path)

//BOUNDARY: Changes with unknown blast radius require explicit acknowledgment.

---

### Capsule: IncrementalExecution

**Invariant**
Make small, verifiable changes; validate before proceeding to next step.

**Example**
Deploying a new app:
1. Create app folder structure → verify files exist
2. Encrypt Secret with SOPS → verify `.sops.yaml` is created
3. Deploy HelmRelease → commit and push to trigger Flux

**Depth**
- Checkpoints: After each logical unit, pause and verify
- Trade-off: Slower execution vs catching issues early
- NotThis: Big-bang deployments that change everything at once
