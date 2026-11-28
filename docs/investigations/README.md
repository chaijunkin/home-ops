# Incident investigations

Incident logs for this cluster are **not** kept in this repository.

They record MAC addresses, firewall rule identifiers, ISP provisioning detail and node topology —
things a public repository has no reason to publish. A review on 2026-11-28 found this repository
otherwise contains no MAC addresses at all, so the logs were the only place that detail was exposed.

The alerting and remediation work those investigations produced is here, and self-contained: what
changed and why is in #2593, #2594, #2604, #2607, #2608 and #2610. The raw evidence trail behind
them — the 2026-11-21 VLAN 31 egress outage — is maintained out-of-tree.
