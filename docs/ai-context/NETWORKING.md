---
description: Network architecture covering Gateway API, HTTPRoute, Envoy Gateway, Cilium IPAM, and DNS resolution paths.
tags: ["GatewayAPI", "EnvoyGateway", "DNS", "Cilium", "Cloudflare"]
audience: ["LLMs", "Humans"]
categories: ["Architecture[100%]", "Networking[100%]"]
---

# Networking Architecture

This document explains the network architecture and traffic flow within the `chaijunkin/home-ops` cluster.

## Ingress Architecture

### Capsule: GatewaySelection

**Invariant**
The cluster strictly uses the Gateway API via Envoy Gateway. Applications are routed through either an internal or external gateway based on security needs.

**Example**
```yaml
# Public internet access
route:
  main:
    parentRefs:
      - name: envoy-external
        namespace: network
        sectionName: https
        
# Internal LAN access only
route:
  main:
    parentRefs:
      - name: envoy-internal
        namespace: network
        sectionName: https
```
//BOUNDARY: Without a valid `parentRefs` pointing to the correct Gateway in the `network` namespace, the HTTPRoute will not process any traffic.

**Depth**
- **Implementation**: The cluster uses Envoy Gateway as the primary Gateway API implementation. `Ingress` objects are deprecated.
- **Trade-off**: `HTTPRoute` is more verbose than `Ingress`, but provides much richer traffic splitting, header modification, and standardization capabilities out of the box.

---

### Capsule: CiliumIPAM

**Invariant**
LoadBalancer IPs are strictly assigned and managed using Cilium IPAM via annotations, not external controllers like MetalLB.

**Example**
```yaml
service:
  app:
    controller: plex
    type: LoadBalancer
    annotations:
      lbipam.cilium.io/ips: 10.10.30.14
```
//BOUNDARY: Omitting the `lbipam.cilium.io/ips` annotation for a LoadBalancer service will either cause it to stay Pending or be randomly assigned an IP from the pool, breaking DNS records.

---

## DNS & Tunneling Architecture

### Capsule: SplitBrainDNS

**Invariant**
The cluster uses a "Split-Brain" DNS architecture powered by three distinct `external-dns` instances to optimize traffic paths based on the client's origin network.

**Example**
When you deploy a public application (like Plex):
1. **Cloudflare `external-dns`**: Syncs the `plex.${SECRET_DOMAIN}` record to Cloudflare, routing external internet traffic through the Cloudflare Tunnel.
2. **AdGuard `external-dns`**: Syncs the exact same `plex.${SECRET_DOMAIN}` record into AdGuard (local DNS). When you are at home, AdGuard intercepts the request and resolves it to the local `envoy-gateway` IP.

//BOUNDARY: This ensures that local traffic never leaves your local network to reach the Cloudflare Tunnel, preserving bandwidth and latency while maintaining public access.

**Depth**
- **Public (Cloudflare)**: Manages external records pointing to Cloudflare Tunnels for secure internet ingress.
- **Local Public-Facing (AdGuard)**: Intercepts public domains when queried on the local network, bypassing the tunnel and routing directly to the local Envoy Gateway. Also provides network-wide ad blocking.
- **Private (Unbound)**: Manages strictly private domains that are never exposed to the public internet, resolving them to the `envoy-internal` gateway.

---

## Troubleshooting

### Check HTTPRoute Status

If an application is unreachable, check if its HTTPRoute is accepted by the Gateway:

```bash
# Get all HTTPRoutes
kubectl get httproutes -A

# Describe a specific route to check the 'Accepted' status
kubectl describe httproute <name> -n <namespace>
```

### Check Envoy Logs

```bash
# Get logs from Envoy Gateway
kubectl logs -n network -l app.kubernetes.io/name=envoy-gateway
```
