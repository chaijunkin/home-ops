# TODO

## Infrastructure & Observability Reminders

- [ ] **Talos Kernel Configuration (eBPF Profiling):**
  - Run `terraform apply` on the Proxmox/Talos Terraform configuration to apply the `kernel.kptr_restrict: 0` sysctl change to the cluster nodes.
  - Once the nodes are updated, re-enable `ebpf: true` in `kubernetes/apps/observability/k8s-monitoring/app/helmrelease.yaml` to turn on Grafana Alloy's zero-code continuous profiling.
  - Verify if `alloy-profiles` daemonset starts successfully without the `kallsyms` permission error.

- [ ] **AI Observability (Grafana):**
  - If granular GenAI metrics (`gen_ai_client_token_usage_total`, etc.) are needed beyond what LiteLLM provides natively, consider deploying **OpenLit** as an SDK/sidecar for OpenCode and LiteLLM.
  - Check the `Agent Observability (OTel GenAI)` dashboard to ensure metrics are populating correctly via the Alloy receiver.

- [ ] **Application-Level Profiling (Alternative to eBPF):**
  - If eBPF profiling continues to be blocked by Talos kernel restrictions, integrate the Pyroscope SDK directly into your apps:
    - **OpenCode (Node.js):** `npm install @grafana/pyroscope-nodejs`
    - **LiteLLM (Python):** `pip install pyroscope-io`
