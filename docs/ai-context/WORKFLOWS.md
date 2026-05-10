---
description: Operational rules, GitOps pipelines, secrets management, and Taskfile enforcement.
tags: ["GitOps", "Flux", "Taskfile", "Flyio", "SOPS"]
audience: ["LLMs", "Humans"]
categories: ["Workflows[100%]", "Operations[100%]"]
---

# Operational Workflows

This document defines the operational rules and GitOps workflows for the `chaijunkin/home-ops` repository.

## Operational Standards

### Capsule: GitOpsReconciliation

**Invariant**
Cluster state converges to match Git; Flux reverts manual changes. Do not attempt to bypass GitOps for permanent changes.

**Example**
You edit a deployment via `kubectl edit deployment my-app`. Within an hour, Flux detects the drift and overwrites your changes with the state defined in Git.
//BOUNDARY: If you need to make a permanent change, commit it to Git. Only use `kubectl edit` for temporary emergency debugging.

**Depth**
- **Distinction**: GitOps is declarative; `kubectl` is imperative.
- **Trade-off**: GitOps provides an audit trail and disaster recovery at the cost of slower feedback loops during active development.

---

### Capsule: TaskfileEnforcement

**Invariant**
Do **NOT** use manual commands like `kubectl apply` or `flyctl deploy` directly unless specifically debugging. Always use `Taskfile` (`task`) to run operations.

**Example**
```bash
# CORRECT
task kubernetes:kubeconform

# WRONG
kubeconform -strict -summary -output json kubernetes/...
```
//BOUNDARY: Using raw commands risks missing critical environment variables or pipeline steps defined in the Taskfile.

**Depth**
- **Modularity**: Tasks are not all stored in the root `Taskfile.yaml`. They are highly modularized inside the `.taskfiles/` directory (e.g., `.taskfiles/kubernetes`, `.taskfiles/talos`, `.taskfiles/sops`, `.taskfiles/fly`).
- **Command Discovery**: Run `task --list` to see all available automated tasks.

---

### Capsule: FlyioAppDeployment

**Invariant**
Fly.io apps are strictly managed via `task fly:app:*` commands, using isolated `.config.env` files located in their respective directories.

**Example**
To deploy `gatus` to Fly.io:
```bash
task fly:app:deploy APP=gatus
```
//BOUNDARY: Do not manually run `flyctl deploy` from the root directory or manually export variables. The Taskfile orchestrates loading the correct `infrastructure/flyio/gatus/.config.env` before running the deployment.

---

### Capsule: ContinuousIntegration

**Invariant**
Every Pull Request is automatically validated by GitHub Actions using `flux-local` to ensure manifests are valid and to provide a diff of the planned changes.

**Example**
You create a PR updating a HelmRelease. The `Flux Local - Diff` action runs and posts a comment to the PR showing exactly which fields in the rendered Kubernetes manifests will change.

**Depth**
- **Validation**: CI runs `flux-local test` to ensure all Helm charts in the repo render successfully.
- **Confidence**: Agents should always create Pull Requests rather than pushing to main, as CI provides a safety net against malformed YAML or invalid Helm values.

---

### Capsule: MakejinjaBootstrap

**Invariant**
The cluster's core structure and secrets are bootstrapped using `makejinja`. Templates are stored in `./bootstrap/templates` and rendered into the root directory.

**Example**
You modify a global variable in `config.yaml`. To apply this to the repository, you run `task configure`, which invokes `makejinja` to re-render the cluster manifests from the bootstrap templates.

**Depth**
- **Entry Point**: The `Taskfile.yaml` in the root contains the `.template` and `configure` tasks that orchestrate this flow.
- **Overrides**: Local specific overrides are managed in `./bootstrap/overrides`.

---

## Quick Command Reference

| Task | Command |
|------|---------|
| Validate Manifests | `task kubernetes:kubeconform` |
| Encrypt Secrets | `task sops:encrypt` |
| Check Fly App Logs | `task fly:app:logs APP=<name>` |
| Deploy Fly App | `task fly:app:deploy APP=<name>` |
| Initialize Talos IaC | `task talos:init` |
| Apply Talos config | `task talos:apply` |
