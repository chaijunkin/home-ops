# Findings — VPN_SERVICES_LAN egress outage

**Status:** root cause narrowed to the **VPN provider's end of the tunnel**. Every local component
is now *verified good* over the OPNsense API (see `results/007`); what remains is a Proton-side
session/server check, which only the account owner can do.
**Outage:** 2026-11-21 08:31 UTC → still firing at capture (~52h), continuous, no flapping.
**Severity:** real data loss, not alert noise.

> **Correction notice.** Earlier revisions of this file concluded traffic "dies before reaching the
> tunnel" and named CrowdSec stale bans or missing outbound NAT as prime suspects. Both are
> **refuted** by the API rule trace in `results/007`: the same probe is logged `match pass` on
> `vlan0.31.1` **and** on `wg2` with its source rewritten to the tunnel address `10.2.0.2`, and all
> four CrowdSec ban tables hold zero items. The chain of evidence below replaces that reasoning.

## Answer to "why is my alert firing"

`BlackboxProbeFailed` and `VpnProbeFailed` are **true positives and correctly scoped**. Blackbox is
working as designed: it is reporting that every pod pinned to the VPN VLAN has lost internet egress.

The fault is **not** any of the usual suspects:

| Ruled out | Evidence |
|---|---|
| The probe targets | `1.1.1.1` + `one.one.one.one` both reachable from the normal pod network (16ms / 200 OK) |
| Prometheus / blackbox config | rule is a plain `probe_success == 0`; both exporters behave differently on identical targets |
| The `Completed` blackbox pod | 16-day-old drain leftover; both Deployments 1/1 Available |
| The Proton tunnel | peer up, handshake 67s ago, gateway monitor **0% loss, 14.1ms RTT** |
| CARP / HA VIP failover | `carp_allowed=1`, `demotion=0`, `maintenance_mode=0` |
| Cluster DNS | resolves in 0.010s from the VPN-pinned pod |
| A GitOps change | zero commits in this repo 2026-11-19→23 |
| macvlan attachment | `net1` present with `10.10.31.20`, pod↔pod on VLAN works |
| The node reboot as cause | outage began 08:31Z, reboot was 09:50Z, and the reboot did not clear it |
| L2 / VLAN trunking / interface down | firewall ARP holds `10.10.31.20 → da:23:25:78:a1:24` (the pod's exact annotation MAC), fresh on `VPN_SERVICES_LAN`. **ARP sits below pf**, so frames arrive |
| **A CrowdSec ban** | all four `crowdsec*` aliases: `current_items=0`, `in_block_p=0`, `out_block_p=0`. CrowdSec is stopped, but blackholes nothing |
| **Traffic being blocked by pf** | log shows `match pass` for `10.10.31.20 → 1.1.1.1/1.0.0.1` (icmp **and** tcp) on `vlan0.31.1`, rule 145 |
| **Missing policy route** | the same probe is then logged on **`wg2`** as rule 110 — never on `pppoe0` |
| **Missing outbound NAT** | on `wg2` the source is rewritten to the tunnel address **`10.2.0.2`**, for ICMP and TCP/443 alike |
| A recent config change | every VPN rule + the NAT rule date to **2025-11-18/19**; WG persisted **2026-01-03** |
| Stale pf states | ICMP/TCP states expire in ~30–75s; fresh flows fail identically 52h on |
| A CARP/HA split | `<hasync>` unconfigured; VLAN 31 gateway MAC `60:be:b4:05:0a:b9` is physical, not a vhid |
| MTU / MSS clamping | 92-byte ICMP and a 60-byte SYN both fail; MSS clamping is already configured |

## What is actually broken

**Everything on the firewall is verified correct; the tunnel accepts our packets and returns
nothing.** The provider's end of the WireGuard tunnel is the boundary of the failure.

Chain of evidence (full capture in `results/007`):

1. Pods' frames reach the firewall — ARP entry present and fresh; pf logs them.
2. pf **passes** them: rule 145 = config rule `5ad2f102` "Allow routing through WAN protonvpn",
   `source ProtonVPN_WG_VPN_Hosts → destination !Private_Network`, `gateway
   WAN_ProtonVPNSingapore`, `keep state`, `log`.
3. The policy route **is** applied — the identical flow appears on `wg2`, not `pppoe0`.
4. Outbound NAT **is** applied — source becomes `10.2.0.2`, the tunnel's own address.
5. **No reply ever arrives.** Zero `1.0.0.1/1.1.1.1 → …` log entries; `vlan0.31.1` carries
   70 B/s pods→firewall but only 12 B/s firewall→pods (would be symmetric if replies came back).
6. The tunnel's control plane is healthy throughout: handshake 67–111s ago, `wg2` tx/rx at
   handshake+keepalive scale, `disableroutes=1` + `fargw=1` as designed.

### Why "gateway online, 0% loss, 13 ms" misled the triage for two days

`<monitor/>` is **empty** on `WAN_ProtonVPNSingapore`, so OPNsense monitors `10.2.0.1` — **Proton's
own end of the tunnel** — not the internet. Confirmed two ways: `10.2.0.2 → 1.1.1.1` log lines
appear *only* paired with our 30s probes (never at the ~10s monitor cadence), and a `10.2.0.1` ping
cannot be logged at all because floating rule #0 requires `destination NOT opt12`. A gateway can
therefore report perfect health while forwarding zero customer traffic. **This is the single most
important lesson in this document.**

## Where the fault is

The peer endpoint is pinned to a literal server IP **`149.50.211.164:51820`** and the tunnel address
is hardcoded **`10.2.0.2/32`**, both unchanged since Jan 2026. Proton's status page shows no
incident for Nov 20–22, but does list a **"Global ProtonVPN infrastructure upgrade campaign,
Aug 31 2026 → Nov 30 2026"** that is replacing paid servers and deprecating previously downloaded
configs — the same window in which this path died. A server migrated under a pinned config, or a
reassigned tunnel address, produces exactly this signature: handshake still succeeds (keys are
valid), the peer still answers its own gateway IP, forwarded customer traffic silently vanishes.

**Residual uncertainty (stated honestly):** "replies arrive at `wg2` but die during state de-NAT"
is not fully excluded by the API alone; `tcpdump` on `pppoe0`/`wg2` (script 007 §8) would settle it.
That failure mode is exotic and would not have survived a reboot, so it ranks far below the
provider-side explanation.

## Resolution plan (in cost order — nothing here is a firewall reboot)

1. **Localize in 2 minutes, zero changes.** Connect to Proton VPN from a laptop or phone on the
   *same* ISP connection (official app, or a freshly downloaded WireGuard config).
   - Works → Proton's service is fine, so the firewall's stored copy is stale → step 3.
   - Fails too → account/session-level problem → step 4.
2. **Free attempt.** In OPNsense: **VPN → WireGuard → Configuration → reload the
   `ProtonVPN-ExitSingapore` instance** (or disable then re-enable the peer). VLAN 31 has been dead
   52h, so this can only help. It does not touch `wg1` (home WG) or any other VLAN.
3. **The fix if the config is stale.** Proton dashboard → VPN → WireGuard downloads → fresh config
   for a Singapore server → update the OPNsense **endpoint** (public key + server address + port)
   *and* the **instance tunnel address** together from that file, then save. Do not hand-edit the
   endpoint IP alone: each Proton server has its own public key, so a mismatched key kills the
   handshake and turns a one-VLAN outage into a tunnel that won't come up at all.
4. **Account check** while there: active plan, active WireGuard device/session count, and delete +
   re-create the OPNsense device entry in the Proton dashboard.
5. **Then, separately:** restart CrowdSec — there has been no IPS for ~52h, which is its own incident.

### Verification loop I can run read-only once a step is applied

`probe_success 1` on the VPN exporter → `10.2.0.1`-path healthy → `vlan0.31.1` back to ~5–6 kB/s
and roughly symmetric rx/tx → `wg2` carrying real volume → `BlackboxProbeFailed` +
`VpnProbeFailed` resolve → `slskd-0` traffic back above 1 kB/s → re-check the 22
`KubeHpaMaxedOut` alerts.

Do **not** "fix" this by loosening the alert — it caught a 26-hour silent outage of your download
stack. If anything it under-alerted: ~26h with no escalation, and `startsAt` (10:13Z) read ~1h40m
later than the real start (08:31Z) because Prometheus restarted mid-event.

## Follow-ups worth tracking

- Re-check the 22 `KubeHpaMaxedOut` alerts after egress returns — likely collateral, not capacity.
- Consider alerting on `up{instance="gateway.cloudjur.com:9100"}`: the firewall going dark at 08:37Z
  was the earliest, least ambiguous signal, and nothing paged on it.
- The `Completed` pod `blackbox-exporter-7cc867c9d5-9tlp2` and 7 stale ReplicaSets are harmless but
  confusing on a triage; clean up when convenient.

## Method notes for future triages in this repo

- `prometheus-kube-prometheus-stack` containers have **no `wget`/`curl`**; the alertmanager container
  does. For Prometheus, `kubectl port-forward` and query locally.
- Prometheus HTTP responses key series as **`metric`**, not `labels`; `query_range` needs absolute
  epoch `start`/`end`, not `-60h`.
- `node_exporter` uses `node_network_receive_bytes_total`, **not** `..._received_...` (the typo
  silently returns no data).
- The cluster is **single-node**, so macvlan `bridge` pod↔pod connectivity is in-kernel and proves
  nothing about the physical uplink or gateway.
- Probing private IPs via `blackbox-exporter` is refused by its IP-range restriction — a failure
  there is the exporter, not the network. Probe private targets on the exporter whose config allows them.
- `kubectl get --raw /api/v1/namespaces/<ns>/services/<svc>:<port>/proxy/probe?target=…&debug=1` is
  the fastest read-only way to get a live probe with phases, no port-forward needed.
