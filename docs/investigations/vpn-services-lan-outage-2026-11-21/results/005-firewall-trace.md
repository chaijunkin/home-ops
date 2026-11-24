# 005 — Where it dies: firewall trace + counters

## Blackbox debug traces (from `blackbox-exporter-vpn`)

ICMP to `1.1.1.1`:

```
probe_icmp_duration_seconds{phase="resolve"} 3.756e-06
probe_icmp_duration_seconds{phase="setup"}   0.00021602
probe_icmp_duration_seconds{phase="rtt"}     0        <- request sent, zero replies
probe_timeout_seconds 5
probe_success 0
```

HTTPS to `one.one.one.one`:

```
probe_dns_lookup_time_seconds            0.010425385   <- DNS works fine
probe_http_duration_seconds{phase="resolve"}   0.010425385
probe_http_duration_seconds{phase="connect"}   0        <- connect NEVER started
probe_http_duration_seconds{phase="tls"}       0
probe_http_duration_seconds{phase="transfer"}  0
probe_http_status_code 0
probe_success 0
```

`connect = 0` with total elapsed ~0.52s is the discriminator: the connect syscall **errored
immediately** rather than timing out. Combined with working DNS and correct routes, the pod has
no usable path to its next hop `10.10.31.1` — and `10.10.31.1` itself does not answer ICMP
(5.003s, script 002).

## Firewall counters for VPN_SERVICES_LAN (1h increase, IPv4)

| interface | pass | block (in) | block (out) |
|---|---|---|---|
| `pppoe0` (WAN) | 6,760,808 | 1,320 | 51 |
| `igc2` (LAN) | 7,085,805 | 380 | 0 |
| `vlan0.30.2` (INFRA_LAN) | 2,748,440 | 26 | 107 |
| **`vlan0.31.1` (VPN_SERVICES_LAN)** | **1,119** | **40** | 0 |
| `vlan0.32.1` (NOT_LAN) | 402 | 2,373 | 0 |

Everything else on the firewall is processing millions of packets normally. `VPN_SERVICES_LAN`
is down at ~1.1k packets/hr with ~40/hr explicitly blocked — it is being dropped **at** the
interface, not failing somewhere beyond it.

## Two leads on the firewall (not proof)

```
opnsense_services_status{name="crowdsec"} = 0     <- STOPPED
opnsense_services_stopped_total          = 2      (of 31)
opnsense_firmware_needs_reboot           = 1
opnsense_firmware_upgrade_needs_reboot   = 1
```

1. **CrowdSec is stopped.** Its OPNsense bouncer installs pf tables that persist across a service
   stop *and* across a reboot. A stale remediation covering the VPN path fits the signature
   exactly: tunnel healthy, nothing forwarded, block counters on that interface.
2. **Reboot-pending firmware flags** — consistent with firewall / policy-route state coming back
   incompletely after the 09:50Z reboot, i.e. the `VPN_SERVICES_LAN` → `WAN_ProtonVPNSingapore`
   policy route or its outbound NAT rule is missing or orphaned.

Note on NAT specifically: if outbound NAT for the VLAN is gone, packets leave `wg2` with source
`10.10.31.x`, which is outside the tunnel's `10.2.0.0/16`, so Proton drops them — producing
"no reply ever" while the tunnel itself stays perfectly healthy. That matches what we see.

**Both need OPNsense shell access and are outside what this cluster can tell us.**
