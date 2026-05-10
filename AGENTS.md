# Home Operations - AI Assistant Guide

This is a **Home Kubernetes cluster monorepo** managed with GitOps. This repository relies on Infrastructure as Code (IaC) principles.

## 1. Repository Structure & Architecture

### Cluster Architecture
- **Kubernetes**: Uses Talos Linux, providing a secure, minimal, and immutable Kubernetes platform.
- **GitOps Flow**: `Git push` → `Flux source sync` → `Kustomization` → `HelmRelease` → `k8s resources`.
- **External Dependencies**: `Fly.io` is used for certain critical cloud workloads (e.g., Gatus) to ensure they remain accessible even if the local cluster goes down.

### Directories
- `kubernetes/apps/`: Application configurations grouped by category (HelmReleases and Kustomizations).
- `kubernetes/talos/`: Talos Linux machine and cluster configurations.
- `kubernetes/flux/`: Core Flux CD setup for managing the GitOps pipeline.
- `infrastructure/terraform/proxmox/`: Proxmox VM provisioning via Terraform/OpenTofu.
- `infrastructure/ansible/`: Server bootstrapping and setup.
- `infrastructure/flyio/`: Configurations and environments for Fly.io apps.
- `.taskfiles/`: Definitions for all `task` commands.

## 2. Development Conventions & Common Operations

### Taskfile Enforcement
Do **NOT** use manual commands like `kubectl apply` or `flyctl deploy` directly unless specifically debugging. Always use `Taskfile` (`task`) to run operations.
- `task --list`: See available tasks.
- `task kubernetes:kubeconform`: Validate Kubernetes manifests.
- `task sops:encrypt`: Encrypt sensitive files.
- `task fly:app:deploy APP=<name>`: Deploy a Fly app using its specific environment.

### Secrets Management
- **ABSOLUTE PROHIBITION**: NEVER commit plain-text secrets or credentials in Git.
- All secrets MUST be managed via External Secrets or encrypted with SOPS.
- Use `task sops:encrypt` to encrypt sensitive files using age keys before committing.

## 3. PR Review Standards

### HelmRelease Requirements
- All applications MUST use `HelmRelease` via Flux, avoiding raw manifests wherever possible.
- Pinned chart versions must specify `spec.chart.spec.version`.
- Must include `spec.interval` to define the reconciliation frequency.
- `valuesFrom` should reference ConfigMaps or Secrets rather than hardcoding sensitive values inline.

### Image & Digest Policy
- Prefer `@sha256:` digests over version tags to ensure reproducibility and security.
- Avoid Docker Hub for critical infrastructure components. Preferred registries are `GHCR.io` and `registry.k8s.io`.

### Breaking Change Detection
Always `request_changes` (or flag to user) if:
- API version changes (e.g., `apiVersion: apps/v1beta1` → `apps/v1`).
- Usage of deprecated fields is introduced.
- A major version is bumped without an accompanying justification or changelog review.
- Custom Resource Definitions (CRDs) are modified without caution.

## 4. YAML Sorting Instructions

Whenever modifying or generating YAML files, apply the following strict sorting rules to maintain a consistent code style.

- **Default Rule**: All fields and properties should be sorted alphabetically at every level, unless overridden below.

### Kubernetes Resources
Top-level fields should always be sorted as follows:
1. `apiVersion`
2. `kind`
3. `metadata`
4. `spec`

The items within `metadata` should be sorted as follows:
1. `name`
2. `namespace`
3. `annotations`
4. `labels`

### HelmReleases (app-template)
For HelmReleases utilizing the `app-template` chart (typically indicated by a sidecar `ocirepository` pointing to `oci://ghcr.io/bjw-s-labs/helm/app-template`):

- If an `enabled` field is present, it is always the first field in its section.
- Items within `spec` should be sorted:
  1. `chartRef`
  2. `interval`
  3. `dependsOn`
  4. `install`
  5. `upgrade`
  6. `values`
- Items within `spec.values` should have `defaultPodOptions` (if present) first, followed by alphabetical sorting for sibling keys (e.g., `controllers`, `persistence`, `service`).

**Controllers Sorting (`spec.values.controllers.*`)**:
1. `type`
2. `annotations`
3. `labels`
4. Specific fields (like `cronjob` or `statefulset`)
5. `pod`
6. [Alphabetical keys...]
7. `initContainers` (always last, before `containers`)
8. `containers` (always last)

**Containers Sorting (`spec.values.controllers.*.containers.*`)**:
- `image` must be first, followed by alphabetical sorting.
- Inside `.resources`, `requests` must precede `limits`.

**Persistence Sorting (`spec.values.persistence.*`)**:
1. `type`
2. `annotations`
3. `labels`
4. [Alphabetical keys...]
5. `globalMounts` (last)
6. `advancedMounts` (last)

*Note: Sibling keys within `.persistence.*`, `.service.*`, etc., do NOT need to be alphabetically ordered relative to each other—only the keys within each individual item must follow the rules.*
