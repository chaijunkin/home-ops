# 007 — OPNsense API triage: rules, NAT, tunnel, and the decisive rule trace

Source: `scripts/008-opnsense-api-triage.sh` (GET-only, via pod `observability/opnsense-api-probe`
with `envFrom` on `opnsense-exporter-secret`). Captured 2026-11-23 ~18:35–18:55 local (UTC+8),
≈52h into the outage.

## 0. API access

| Call | Result |
|---|---|
| `GET /api/core/firmware/status` | **200** in 0.15s — authenticated, admin scope |
| works | `firewall/alias/searchItem`, `diagnostics/firewall/log` (GET only), `routing/settings/get`, `core/backup/download/this` |
| 404 | `firewall/nat*`, `plugin/wireguard/*`, `core/service/status`, `diagnostics/state*`, `diagnostics/command_interface/run` |
| **200 on GET** | `firewall/filter/apply` — a MUTATION endpoint that answers GET. See the caveat in script 008. |
| `firewall/filter/get` | returns `{"filter":{"rules":{"rule":[]}}}` — **0 rules**, which is false (pf logs `rulenr` 145/167). An API artifact; read rules from config.xml instead. |

## 1. Live config.xml (`core/backup/download/this`, 312 402 bytes, plaintext)

Interface assignments that matter:

```
opt3   device=vlan0.31.1  descr=VPN_SERVICES_LAN       enable=1  ipaddr=10.10.31.1
opt12  device=wg2         descr=WAN_ProtonVPNSingapore enable=1
wan    device=pppoe0
```

**The rule that carries this traffic** (config rule #23, `uuid 5ad2f102-…`):

```xml
<type>pass</type>       <interface>opt3</interface>
<source><address>ProtonVPN_WG_VPN_Hosts</address></source>     <!-- 10.10.31.1/24 -->
<destination><address>Private_Network</address><not>1</not></destination>
<gateway>WAN_ProtonVPNSingapore</gateway>
<statetype>keep state</statetype>  <direction>in</direction>  <quick>1</quick>  <log>1</log>
<!-- created 2023-11-24, updated 2025-11-19 16:45 -->
```

**Outbound NAT** — `<nat><outbound>`:

```xml
<mode>hybrid</mode>
<rule> <source><network>ProtonVPN_WG_VPN_Hosts</network></source>
       <destination><any>1</any></destination>
       <interface>opt12</interface>        <!-- wg2 -->
       <!-- no <disabled> => ENABLED; created 2025-11-18, updated 2025-11-19 -->
```

**WireGuard** (`OPNsense/wireguard`):

```
server  name=ProtonVPN-ExitSingapore  instance=2 (=wg2)  enabled=1
        tunneladdress=10.2.0.2/32   dns=10.2.0.1   gateway=10.2.0.1
        disableroutes=1   mtu=1420   port=51820
peer    name=ProtonVPN_Singapore    enabled=1
        serveraddress=149.50.211.164:51820   tunneladdress=0.0.0.0/0   keepalive=25
```

**Gateway** `WAN_ProtonVPNSingapore`: `disabled=0`, `interface=opt12`, `gateway=10.2.0.1`,
**`fargw=1`** (far-gateway host route — correct for a WG exit), `monitor_disable=0`,
**`monitor` empty ⇒ the monitor pings the gateway address `10.2.0.1` itself, NOT the internet.**

Other checks: no `<binat>`, no `<onetoone>`, `<staticroutes>` empty, `<hasync>` not configured
(single node — and the VLAN 31 gateway ARP MAC `60:be:b4:05:0a:b9` is physical, not a CARP vhid).
`dhcpd opt3` is enabled, pool `10.10.31.2–254`, dnsserver `10.2.0.1`, one staticmap `mini-pi → .8`
(the pool does overlap the pods' static `.10`/`.20`, but ARP shows no collision — not the cause).

**Nothing in the VPN path was edited recently**: every VPN rule and the NAT rule dates to
**2025-11-18/19**, the WG section persisted **2026-01-03**. Config is not the trigger.

## 2. CrowdSec is NOT the blocker

```
crowdsec_blacklists   current_items=0  in_block_p=0  out_block_p=0
crowdsec_blocklists   current_items=0  in_block_p=0  out_block_p=0
crowdsec6_blacklists  current_items=0  ...
crowdsec6_blocklists  current_items=0  ...
```

Every alias with a non-zero counter:

```
Private_Network        in_p=110,969,364  out_p=73,569,004
ProtonVPN_WG_VPN_Hosts in_p=      40,909  out_p=33,677  eval_match=33,801  blocks=0
Printer                in_b=195   midnight_silent_device_ip in_b=19
```

CrowdSec *is* stopped (`opnsense_services_status{name="crowdsec"}=0`) — a real problem, no IPS for
~50h — but its tables are empty, so it blackholes nothing. Full stopped list is only
**`crowdsec` + `iperf`** (iperf is an intentionally idle test daemon).

## 3. THE DECISIVE TEST — 24 probes at `1.0.0.1` via the VPN-pinned exporter

`1.0.0.1` was chosen because the gateway monitor never pings it, so nothing else can appear in the
log as this traffic. Result, per probe, **in matching pairs**:

```
18:50:47 iface=vlan0.31.1  match/pass  10.10.31.20 -> 1.0.0.1  icmp        rule=145
18:50:47 iface=wg2         match/pass  10.2.0.2    -> 1.0.0.1  icmp        rule=110
18:50:46 iface=vlan0.31.1  match/pass  10.10.31.20 -> 1.0.0.1  icmp        rule=145
18:50:46 iface=wg2         match/pass  10.2.0.2    -> 1.0.0.1  icmp        rule=110
...   13 ICMP pairs ...
18:50:23 iface=vlan0.31.1  match/pass  10.10.31.20 -> 1.0.0.1  tcp  dport=443  rule=145
18:50:23 iface=wg2         match/pass  10.2.0.2    -> 1.0.0.1  tcp  dport=443  rule=110
```

Interface totals in the same window: `igc2 264, pppoe0 373, vlan0.30.2 280, wg2 17, vlan0.31.1 17`.

**What this proves — the entire local chain is correct:**

1. pf **passes** the pod's traffic (rule 145 = config rule #23). *Not blocked. No ban, no policy gap.*
2. The **policy route works**: the flow appears on `wg2`, never on `pppoe0`.
3. **Outbound NAT works**: the source is rewritten `10.10.31.20 → 10.2.0.2`, the tunnel's own
   address — for both ICMP and TCP/443.
4. **Nothing ever answers.** Zero `1.0.0.1 → …` / `1.1.1.1 → …` entries anywhere in the log; the
   probes die in the connect/echo phase.

The only `pppoe0` entries involving `1.0.0.1` are `210.186.239.63 → 1.0.0.1 tcp/853` — the
firewall's own DNS-over-TLS out the plain WAN. Unrelated.

## 4. Return path is measurably empty

```
vlan0.31.1  rx (pods -> firewall)   70.12 B/s
vlan0.31.1  tx (firewall -> pods)   12.43 B/s      <- would be ~symmetric if replies arrived
wg2         tx 139.26 B/s   rx 76.45 B/s  (1.25 / 1.18 pkt/s — handshake + keepalive scale)
```

## 5. Why "gateway online, 0% loss, 13ms" misled us

`<monitor/>` is empty, so OPNsense monitors **`10.2.0.1` — Proton's end of the tunnel**, not the
internet. Confirmed independently by the log: `10.2.0.2 → 1.1.1.1` lines appear *only* paired with
our pod probes at our 30s probe interval, never every ~10s. And a `10.2.0.1` ping is *not* logged,
because floating rule #0 requires `destination NOT opt12` and `10.2.0.1` **is** in `opt12`.
So `opnsense_gateways_status{name="WAN_ProtonVPNSingapore"} = 1` proves only that the peer answers
its own gateway — consistent with a tunnel that handshakes but forwards nothing.

## 6. Conclusion

**Every local component is verified good**: L2/ARP, the VLAN interface, the filter rule, the
policy route to `WAN_ProtonVPNSingapore`, outbound NAT on `opt12`, and the WireGuard tunnel's
control plane. Our packets demonstrably leave the firewall through the tunnel with the correct
source address, and the provider returns nothing — for ~52h, across all VLAN 31 pods, unaffected by
a firewall reboot and by a ruleset re-apply.

The break is at the **Proton end of the tunnel**, and the config's fragility is visible: the peer
endpoint is pinned to a literal server IP `149.50.211.164` and the tunnel address is hardcoded
`10.2.0.2/32`, both unchanged since Jan 2026. Proton's status page shows no incident for Nov 20–22
but does list a **"Global ProtonVPN infrastructure upgrade campaign, Aug 31 2026 → Nov 30 2026"**
replacing paid servers and deprecating previously downloaded configs — the same window in which
this path died.

Residual uncertainty (honest): "replies arrive at `wg2` but die in state de-NAT" cannot be fully
excluded from the API alone. Distinguishing it needs `tcpdump` on `pppoe0`/`wg2` (script 007 §8).
That failure mode would be exotic and would not have survived a reboot, which is why it ranks well
below the provider-side explanation.
