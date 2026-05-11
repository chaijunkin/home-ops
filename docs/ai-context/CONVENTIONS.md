---
description: Coding standards, YAML sorting rules, image pinning, and standard app patterns.
tags: ["Conventions", "YAML", "AppTemplate", "SOPS", "Makejinja"]
audience: ["LLMs", "Humans"]
categories: ["Conventions[100%]", "Reference[90%]"]
---

# Conventions Context

This document enforces strict coding standards, YAML sorting rules, and Git operations.

## Deployment Standards

### Capsule: StandardAppPattern

**Invariant**
Standard applications MUST use `bjw-s/app-template` and must include `gethomepage.dev` annotations for dashboarding and `gatus` annotations for uptime monitoring on their Envoy Gateway routes.

**Example**
```yaml
spec:
  chartRef:
    kind: OCIRepository
    name: app-template
  values:
    # ... controllers, containers, etc ...
    route:
      app:
        hostnames:
          - app.${SECRET_DOMAIN}
        parentRefs:
          - name: envoy-internal
            namespace: network
            sectionName: https
        annotations:
          gethomepage.dev/enabled: "true"
          gethomepage.dev/group: Media Service
          gethomepage.dev/name: AppName
          gethomepage.dev/description: App Description
          gatus.home-operations.com/endpoint: |-
            conditions: ["[STATUS] == 200"]
```
//BOUNDARY: Do not create raw `Deployment`, `Service`, and `HTTPRoute` resources for standard apps. Always wrap them in the `app-template` values object.

**Depth**
- **Consistency**: Using the annotations on the `route` object ensures that Gatus and Homepage dynamically detect the application without needing manual config updates in their respective charts.

---

### Capsule: FluxKustomizationWrapper

**Invariant**
Apps are deployed using a Flux Kustomization wrapper (`ks.yaml`) which points to subdirectories (like `app/`, `config/`) containing the actual HelmReleases and ConfigMaps.

**Example**
```
kubernetes/apps/ai/toolhive/
├── ks.yaml         # Flux Kustomization (entry point)
├── app/            # Application manifests
│   ├── helmrelease.yaml
│   └── externalsecret.yaml
└── config/         # ConfigMaps
```

**Depth**
- **Distinction**: `ks.yaml` is the entry point read by the root Flux kustomization.
- **Dependencies**: `ks.yaml` allows you to strictly define `dependsOn` (e.g., wait for the database to be ready before deploying the app).

---

### Capsule: FluxDependsOn

**Invariant**
Flux `Kustomization` and `HelmRelease` resources MUST explicitly define their dependencies via `dependsOn` to ensure correct reconciliation order.

**Rules**
- **Storage**: Apps using OpenEBS or Local Hostpath MUST depend on their respective storage provider in `storage`.
- **Volsync**: Apps using the `volsync` component MUST depend on `openebs` in `storage`.
- **Secrets**: Apps using `ExternalSecret` SHOULD depend on `external-secrets-stores` in `kube-system` (Optional).
- **Databases**: Apps using Postgres SHOULD depend on `cloudnative-pg-cluster` in `database` (Optional).
- **Caching**: Apps using Redis/Dragonfly SHOULD depend on `dragonfly-cluster` in `database` (Optional).
- **Authentication**: Apps using SSO (Authentik) SHOULD depend on `authentik` in `security` (Optional).
- **Backups**: Apps using `volsync` SHOULD depend on `volsync` in `volsync-system` (Optional).
- **Sub-Apps**: Sidecar or utility Kustomizations SHOULD depend on the main application Kustomization.



**Example**
```yaml
spec:
  dependsOn:
    - name: external-secrets-stores
      namespace: kube-system
    - name: cloudnative-pg-cluster
      namespace: database
```


---

### Capsule: MultusNetworkAttachment

**Invariant**
If an application needs to reach physical network VLANs (like IoT or VPN devices) without traversing the cluster's overlay routing, it must request attachment via the `k8s.v1.cni.cncf.io/networks` annotation.

**Example**
```yaml
spec:
  values:
    defaultPodOptions:
      annotations:
        k8s.v1.cni.cncf.io/networks: |
          [{
            "name":"multus-iot",
            "namespace": "network",
            "ips": ["10.10.33.254"]
          }]
```
//BOUNDARY: Without this annotation, the pod will remain completely isolated inside the Cilium overlay network and will fail to discover physical mDNS or broadcast devices.

**Depth**
- **IP Addressing**: It is best practice to define static IPs when requesting a Multus attachment to prevent collisions.

---

### Capsule: FluxComponentInjection

**Invariant**
Cross-cutting concerns (like Backups, SSO, and Autoscaling) MUST NOT be manually defined in an app's HelmRelease. They must be injected via Kustomize components in the app's `ks.yaml`.

**Example**
```yaml
# Inside ks.yaml
spec:
  path: ./kubernetes/apps/media/plex/app
  postBuild:
    substitute:
      VOLSYNC_CAPACITY: 20Gi
  components:
    - ../../../../components/volsync
```
//BOUNDARY: Do not manually scaffold `ReplicationSource` objects or manually add Envoy `ext-auth` filters to an app. Always use the predefined components in `kubernetes/components/`.

**Depth**
- **Available Components**: Common components include `volsync` (local/remote backups), `volsync-no-r2` (local only), `envoy-oidc` (Native OIDC client), `ext-auth` (ForwardAuth via Authentik Outpost), and `keda` (Autoscaling).
- **Configuration**: Components use `postBuild.substitute` variables (like `VOLSYNC_CAPACITY` or `APP`) to accept dynamic configuration from the `ks.yaml`.
- **Auth Choice**: Use `envoy-oidc` for applications that require their own dedicated Authentik app; use `ext-auth` for quick, generic protection of internal services via the shared outpost.

---

## Critical Operations

### Capsule: MakejinjaDelimiters

**Invariant**
When working with `.j2` Makejinja templates, you MUST use `#{var}#` syntax instead of the standard `{{var}}`.

**Example**
```yaml
# CORRECT
hostname: #{ inventory_hostname }#

# WRONG
hostname: {{ inventory_hostname }}
```
//BOUNDARY: Using `{{}}` will cause severe templating conflicts with Ansible and Helm, which natively use those delimiters.

---

### Capsule: ImageDigestPinning

**Invariant**
All container images must be pinned using their `@sha256:` digest. Tags alone are strictly prohibited.

**Example**
```yaml
# CORRECT
image:
  repository: ghcr.io/k8s-at-home/home-assistant
  tag: 2024.1.0@sha256:abc123def456...

# WRONG
tag: latest
tag: 2024.1.0
```
//BOUNDARY: Using a tag without a digest breaks the immutability guarantee, meaning a compromised upstream tag could instantly infect the cluster.

---

### Capsule: SopsSecretEncryption

**Invariant**
Secret files must end with the `.sops.yaml` extension and must be encrypted using `sops` (via `task sops:encrypt`) before being committed.

**Example**
```yaml
# A valid SOPS file looks like this in Git:
apiVersion: v1
kind: Secret
stringData:
    password: ENC[AES256_GCM,data:...,iv:...,tag:...,type:str]
sops:
    kms: []
...
```
//BOUNDARY: Committing a plain-text secret compromises the entire repository and requires complete credential rotation.

---

## YAML Sorting Instructions

Whenever modifying or generating YAML files, apply the following strict sorting rules:

**Default Rule**: All fields and properties should be sorted alphabetically at every level, unless overridden below.

### Kubernetes Resources
Top-level fields should always be sorted as follows:
1. `apiVersion`
2. `kind`
3. `metadata`
  1. `name`
  2. `namespace`
  3. `annotations`
  4. `labels`
4. `spec`

### HelmReleases (app-template)
For HelmReleases utilizing the `app-template` chart:
- If an `enabled` field is present, it is always the first field in its section.
- Items within `spec` should be sorted:
  1. `chartRef`
  2. `interval`
  3. `dependsOn`
  4. `install`
  5. `upgrade`
  6. `values`
- Items within `spec.values` should have `defaultPodOptions` first, followed by alphabetical sorting for sibling keys.

**Controllers (`spec.values.controllers.*`)**:
1. `type`
2. `annotations`
3. `labels`
4. Specific fields (`cronjob`, `statefulset`)
5. `pod`
6. [Alphabetical keys...]
7. `initContainers` (always last, before containers)
8. `containers` (always last)

**Containers (`spec.values.controllers.*.containers.*`)**:
- `image` must be first.
- Inside `.resources`, `requests` must precede `limits`.

**Persistence (`spec.values.persistence.*`)**:
1. `type`
2. `annotations`
3. `labels`
4. [Alphabetical keys...]
5. `globalMounts` (last)
6. `advancedMounts` (last)
