---
description: Talos/Proxmox cluster GitOps architecture covering Flux reconciliation, cloud dependencies, and namespaces.
tags: ["GitOps", "Proxmox", "Talos", "Flux", "Flyio", "Ansible"]
audience: ["LLMs", "Humans"]
categories: ["Architecture[100%]", "Reference[90%]"]
---

# Architecture Context

This document outlines the physical and logical architecture of the `chaijunkin/home-ops` repository.

## Core Architecture Patterns

### Capsule: StorageArchitecture

**Invariant**
Storage is layered: Proxmox/Ansible manages bulk NAS storage natively, while Kubernetes uses specific CSI drivers for block/cache storage and NFS clients for bulk consumption.

**Example**
```yaml
# A media app mounting bulk storage
persistence:
  media:
    type: nfs
    server: smb.cloudjur.com
    path: /tank/Storage
```
//BOUNDARY: Do not attempt to run a hyper-converged storage engine like Rook-Ceph for bulk storage. Bulk storage is strictly managed by Ansible on Proxmox.

**Depth**
- **Bulk Storage (`/tank`)**: Managed natively by Proxmox. Ansible configures the NFS/SMB exports. Apps consume this via the `csi-driver-nfs` client or direct `nfs` volume mounts.
- **`democratic-csi`**: Used for `volsync` snapshots and normal stateful storage. It runs on the host SSD boot drive.
- **`openebs`**: Used on secondary drives. Used specifically for cache or heavy write workloads.
- **`garage`**: Provides S3-compatible object storage.

---

### Capsule: CoreInfrastructure

**Invariant**
The cluster relies on Cilium for networking, Envoy Gateway for routing, and Spegel for image caching.

**Example**
When a pod starts, it pulls its image from `ghcr.io`. Spegel caches this image on the node. When the same image is needed on another node, Spegel serves it locally, saving external bandwidth.

**Depth**
- **`cilium`**: The primary CNI. It also provides LoadBalancer IPAM (`lbipam.cilium.io/ips`).
- **`envoy-gateway`**: The Gateway API controller.
- **`spegel`**: P2P image caching across Talos nodes.
- **`intel-device-plugin`**: Enables QuickSync GPU passthrough for media encoding (Plex/Jellyfin).

---

### Capsule: FlyioResilience

**Invariant**
Critical external workloads must run on Fly.io to ensure observability and alerting remain functional even if the local Proxmox host or internet connection fails.

**Example**
`gatus` (uptime monitoring) is deployed via `task fly:app:deploy APP=gatus`. If the local cluster goes offline, `gatus` running on Fly.io detects the outage and sends an alert.
//BOUNDARY: If you move `gatus` into the local cluster, you lose the ability to receive alerts when the local cluster loses power.

### Capsule: SecurityArchitecture

**Invariant**
Internal applications are protected by Single Sign-On (SSO) via Authentik, integrated directly at the routing layer using Envoy Gateway's `SecurityPolicy` CRD.

**Example**
You have two primary paths for securing an application:
1. **Native OIDC (`components/envoy-oidc`)**: Envoy Gateway acts as the OIDC client. Best for apps where you want a direct OIDC flow to a specific Authentik application.
2. **External Auth (`components/ext-auth`)**: Envoy Gateway uses ForwardAuth to check with the Authentik Outpost proxy (`ak-outpost-proxy-outpost-external`) on every request. Best for generic protection of legacy or internal apps.

**Depth**
- **Implementation**: Both paths use the `SecurityPolicy` CRD to attach security rules to an `HTTPRoute`.
- **Dynamic Configuration**: These components use `postBuild.substitute` variables (like `${APP}`) to automatically generate the correct issuer URLs and client secrets.
- **Outposts**: The `ext-auth` component targets the Authentik proxy outpost running in the `security` namespace on port 9000.

---

### Capsule: MultusVLANIsolation

**Invariant**
Pods can bypass the standard Kubernetes overlay network and attach directly to physical hardware VLANs (e.g., IoT, NoT, Trust, VPN) using Multus CNI with MacVLAN and Source Based Routing (SBR).

**Example**
You deploy an IoT controller (like Home Assistant or MQTT) and need it to discover devices on the IoT subnet. By applying the Multus `network-attachment-definition` annotation, the pod gets a secondary IP directly on the physical IoT VLAN (e.g., `10.10.33.x`).

//BOUNDARY: Standard pods are isolated in the Cilium overlay. Do not attempt to route physical broadcast traffic through Envoy Gateway; use Multus to bridge the pod to the required VLAN.

**Depth**
- **Implementation**: Managed in `kubernetes/apps/network/multus/config`. Definitions map `eth3` (or the respective interface) to MacVLAN subnets.
- **Use Cases**: Essential for mDNS/broadcast discovery, separating untrusted NoT devices, or forcing traffic through a VPN tunnel.

---

## Namespaces 

The `kubernetes/apps` directory is organized into the following logical namespaces:

| Namespace | Purpose |
|-----------|---------|
| `actions-runner-system` | Self-hosted GitHub Actions runners |
| `ai` | LLMs, Ollama, OpenWebUI, and AI agent Toolhives (MCPs) |
| `cert-manager` | Automated TLS certificate provisioning |
| `database` | Stateful databases (CloudNativePG, Dragonfly, Mosquitto) |
| `default` | General unclassified workloads |
| `downloads` | Download clients (Torrent, Usenet) |
| `flux-system` | GitOps controllers, sources, and Kustomizations |
| `games` | Game servers (Minecraft, Palworld, etc.) |
| `home-automation` | Home Assistant, Node-RED, Zigbee2MQTT |
| `jobs` | Ephemeral or cron-based tasks |
| `kube-system` | Core cluster infrastructure (Cilium, CoreDNS, Spegel) |
| `media` | Plex, Jellyfin, and the *arr stack |
| `network` | Envoy Gateway, External-DNS, Cloudflared |
| `observability` | Prometheus, Grafana, Loki, Alloy |
| `renovate` | Dependency management |
| `security` | Authentik, Authelia, Vault |
| `storage` | CSI drivers (Democratic-CSI, OpenEBS, NFS Client) |
| `system-upgrade` | Automated OS upgrades (Talos) |
| `volsync-system` | Volume replication and backup |
