# Tools Context

This document is a reference for the core tools and frameworks used to manage the repository.

| Category | Tool | Purpose |
|----------|------|---------|
| GitOps | **Flux** | Deploys configurations from Git to Kubernetes. Watches the `kubernetes` folder and applies `HelmReleases` and `Kustomizations`. |
| CI / CD | **Renovate** | Automated dependency updates. Scans the repository and opens PRs for out-of-date images, charts, and dependencies. |
| OS | **Talos Linux** | A modern, minimal OS for Kubernetes nodes, managed via `.taskfiles/talos`. |
| Task Runner | **Taskfile** | The primary orchestration engine for developers (`task --list`). Replaces raw bash scripts and Makefiles. |
| Secrets | **SOPS** | Encrypts YAML files (`.sops.yaml`) securely in Git. Used in conjunction with `External Secrets` for Kubernetes injection. |
| IaC | **Terraform/OpenTofu** | Used to provision Proxmox VMs (`infrastructure/terraform/proxmox/`). |
| Automation | **Ansible** | Used for bootstrapping servers and configuring the Proxmox host natively (e.g., ZFS, NFS, SMB). |
| Cloud Workloads | **Fly.io** | Hosts external resilience apps. Managed via `task fly:app:*` commands using isolated `.config.env` files. |
