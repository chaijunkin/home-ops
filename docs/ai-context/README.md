# AI Context

This directory contains highly specific, focused documentation intended for AI agents (like Claude) and automation tools interacting with the `chaijunkin-home-ops` repository. 

Rather than relying on a monolithic `AGENTS.md` file, context is split into domains to provide the necessary constraints and boundaries for the specific task at hand.

## Navigation

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Physical topology, cluster architecture, and cloud dependencies.
- [CONVENTIONS.md](./CONVENTIONS.md) - Coding standards, YAML sorting rules, image pinning, and PR standards.
- [DOMAIN.md](./DOMAIN.md) - Core domain rules, state machines, and operational invariants.
- [Ethos.md](./Ethos.md) - Documentation philosophy, hard rules, and values.
- [NETWORKING.md](./NETWORKING.md) - Traffic flow, DNS (AdGuard/Unbound), and Gateway API configurations.
- [PLANNING.md](./PLANNING.md) - Collaborative planning lifecycle for AI-assisted work.
- [WORKFLOWS.md](./WORKFLOWS.md) - Operational rules, GitOps pipelines, and Taskfile enforcement.
- [TOOLS.md](./TOOLS.md) - Documentation on the specific tooling in use (Flux, SOPS, Taskfile).

### AI Writing Guides
- [writing-documentation.md](./writing-documentation.md) - Philosophy for writing documentation as wisdom triggers.
- [writing-capsules.md](./writing-capsules.md) - Format specification for token-efficient concept capsules.
- [mermaid-diagram-guide.md](./mermaid-diagram-guide.md) - Reference for diagram type selection and syntax rules.
