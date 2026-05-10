# Homelab Repository Context

GitOps-managed Kubernetes homelab using Flux and Talos.

## Read First

Before planning work or making modifications, review the specialized context files:

1. **@docs/ai-context/README.md** - Overview and navigation
2. **@docs/ai-context/ARCHITECTURE.md** - System architecture & cloud dependencies
3. **@docs/ai-context/CONVENTIONS.md** - Coding standards, YAML sorting, and PR rules
4. **@docs/ai-context/NETWORKING.md** - Traffic flows, DNS, and Gateway API
5. **@docs/ai-context/WORKFLOWS.md** - How to deploy, validate, and use Taskfiles
6. **@docs/ai-context/TOOLS.md** - CLI commands, external services, and IaC tools

## Critical Invariants

### GitOps Reconciliation
**Invariant**: Cluster state converges to match Git; Flux reverts manual changes. Do not attempt to bypass GitOps for permanent changes.

### AppTemplate Chart
**Invariant**: Apps generally use the `bjw-s/app-template` chart; vendor charts are exceptions and should be used only when necessary.

## Non-Obvious Truths

- **Makejinja Delimiters**: When working with Makejinja templates (`.j2`), use `#{var}#` instead of standard `{{var}}` to avoid conflicts with Helm templating.
- **Gateway API Routing**: Use `HTTPRoute` (Gateway API) instead of `Ingress` for main traffic routing.
- **Image Pinning**: Always include the `@sha256:` digest for container image references.
- **SOPS Files**: Secret files must be named `*.sops.yaml` and must be encrypted before committing.

## Quick Reference

| Task | Command |
|------|---------|
| Validate Manifests | `task kubernetes:kubeconform` |
| Encrypt Secrets | `task sops:encrypt` |
| Check Fly App Logs | `task fly:app:logs APP=<name>` |
| Deploy Fly App | `task fly:app:deploy APP=<name>` |
| Initialize Talos IaC | `task talos:init` |
