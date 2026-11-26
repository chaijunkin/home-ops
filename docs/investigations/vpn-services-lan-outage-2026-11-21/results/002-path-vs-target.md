# 002 — Path vs. target isolation

Live probes through the API-server service proxy:

```
=== svc=blackbox-exporter      module=icmp      target=1.1.1.1
probe_duration_seconds 0.016756368
probe_success 1

=== svc=blackbox-exporter      module=http_2xx  target=https://one.one.one.one
probe_duration_seconds 0.16957321
probe_http_status_code 200
probe_success 1

=== svc=blackbox-exporter-vpn  module=icmp      target=1.1.1.1
probe_duration_seconds 5.002655547      <- full 5s timeout, zero replies
probe_success 0

=== svc=blackbox-exporter-vpn  module=http_2xx  target=https://one.one.one.one
probe_duration_seconds 0.52037104
probe_http_status_code 0
probe_success 0

=== svc=blackbox-exporter-vpn  module=icmp      target=10.10.31.1   (the VPN gateway itself)
probe_duration_seconds 5.003014941      <- gateway does not answer either
probe_success 0

=== svc=blackbox-exporter-vpn  module=icmp      target=10.10.31.15  (metube, same VLAN)
probe_duration_seconds 0.001905856
probe_success 1
```

Conclusion: the targets and the cluster's ordinary internet path are healthy. Only traffic
forced through the VPN VLAN fails — and it fails at the **next hop itself**.

## How the VPN path is built

`blackbox-exporter-vpn` Pod spec carries a Multus secondary interface:

```yaml
k8s.v1.cni.cncf.io/networks: |-
  [{ "name": "vpn", "namespace": "network", "ips": ["10.10.31.20/24"] }]
```

`NetworkAttachmentDefinition network/vpn` = `macvlan` on master `eth1`, mode `bridge`,
static IPAM, gateway `10.10.31.1`, and ~31 split routes covering essentially all of IPv4
(`0.0.0.0/5`, `8.0.0.0/7`, `64.0.0.0/2`, `128.0.0.0/3`, …) — i.e. internet is forced out
of that gateway.

Live network-status confirms attachment is fine:

```json
[{"name":"cilium","interface":"eth0","ips":["10.69.0.216"],"default":true,"gateway":["10.69.0.19"]},
 {"name":"network/vpn","interface":"net1","ips":["10.10.31.20"],"gateway":["10.10.31.1"]}]
```

## Two invalid tests, discarded

1. **The `10.10.31.15` success is not a control.** `kubectl get nodes` returns exactly one
   node (`k8s-0`), so macvlan `bridge` mode switched that packet in-kernel. It proves the
   CNI attachment works, not that the physical uplink or gateway is reachable.

2. **Probing private IPs on `blackbox-exporter` is refused**, not timed out by the network:
   `10.10.31.1`, `10.10.31.20` *and* the control `gateway.cloudjur.com` all returned
   `probe_success 0` at exactly 30.00s, while real scrapes show `gateway.cloudjur.com` up.
   That exporter forbids private ranges. Discarded; conclusions rest only on the VPN exporter.
