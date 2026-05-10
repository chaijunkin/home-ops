---
description: Format specification defining the Invariant->Example->Depth structure for token-efficient concept capsules
tags: ["invariant-example-depth", "token-hygiene", "capsule-format", "composition-rules"]
audience: ["LLMs", "Humans"]
categories: ["Documentation[100%]", "Format-Specification[95%]"]
---

# Token Efficient Concept Capsules

Use capsules as 'AI flash cards' to capture understanding in as few tokens as possible.

## Capsule: CapsuleForm

**Invariant**
A capsule states one timeless idea in one line, shows it once, and clarifies only as needed.

**Example**
Name: `GitOpsReconciliation`
Invariant: "Cluster state converges to match Git; manual changes revert on next sync."
Depth: differences vs imperative kubectl; trade-offs; near-miss clarifications.

**Depth**
- Structure is always **Invariant -> Example -> Depth**.
- No versions, release notes, dates, or timeline facts.
- One idea per capsule; split if you need "and."
- Titles are short `CamelCase` nouns.

---

## Capsule: Template

**Invariant**
A minimal template keeps capsules uniform and easy to scan.

**Example**

```markdown
### Capsule: <Name>

**Invariant**
<One timeless sentence. No versions. No dates. <= ~30 tokens.>

**Example**
<Typical use in <= 5 lines.>
<Optional> //BOUNDARY: <Edge that marks the safe limit.>

**Depth**
- <Distinction>
- <Trade-off>
- <NotThis>
- <SeeAlso: Name, Name>
```

**Depth**
- Keep visible text compact; avoid long paragraphs.
- Prefer line-broken bullets over prose walls.
- Keep names stable; reuse them exactly when referenced.

---

# Checklist (non-negotiables)

- [ ] Invariant first, one idea, timeless, <= ~30 tokens.
- [ ] Example concise; include one boundary only if it prevents common errors.
- [ ] Depth clarifies with bullets; no versions or dates.
- [ ] Names are short `CamelCase`; no hyphens, underscores, emoji, or synonyms.
- [ ] Keep text compact and ASCII; favor common words; trim filler.
- [ ] Invariants never change; new understanding becomes a new capsule.
- [ ] End documents with this checklist.
