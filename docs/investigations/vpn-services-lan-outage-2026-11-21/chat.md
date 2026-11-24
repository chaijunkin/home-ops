# VPN_SERVICES_LAN (VLAN 31) egress outage — 2026-11-21

**Ask:** "can you check why my alert is firing? blackbox probe in home-ops, kubectl."

Cluster: `admin@main` (single-node Talos K3s, `k8s-0`). All steps read-only.

---

## Step 1 — What is actually firing? (`scripts/001`)

31 active alerts. Two are blackbox, both `critical`, both on `service="blackbox-exporter-vpn"`:

- `BlackboxProbeFailed` — job `probe/observability/vpn-icmp`, target `1.1.1.1`
- `VpnProbeFailed` — job `probe/observability/vpn-http`, target `https://one.one.one.one`

Both alerts share one expr family; `VpnProbeFailed` fires on `probe_success{service="blackbox-exporter-vpn"} == 0` for 15m
(`kubernetes/apps/observability/exporters/blackbox-exporter/vpn/helmrelease.yaml:51`).

The remaining 29 are `Watchdog` (by design), 22× `KubeHpaMaxedOut` and 4× `KubeJobFailed`
(`ai-inference-smoke-test`, `renovate chaijunkin-discovery`) — unrelated to blackbox.

Red herring ruled out: `blackbox-exporter-7cc867c9d5-9tlp2` sits in `Completed`/`DisruptionTarget=True`.
It is a 16-day-old node-drain leftover; both Deployments are 1/1 Available. Not the cause.

## Step 2 — Isolate target vs. path (`scripts/002`)

Live probed both exporters through the API-server proxy (read-only GET):

| exporter | target | result |
|---|---|---|
| `blackbox-exporter` (pod net) | `1.1.1.1` icmp | **success**, 16ms |
| `blackbox-exporter` (pod net) | `https://one.one.one.one` | **success**, 200 OK, 169ms |
| `blackbox-exporter-vpn` (net1) | `1.1.1.1` icmp | **fail**, 5.003s (full timeout) |
| `blackbox-exporter-vpn` (net1) | `https://one.one.one.one` | **fail**, status 0, 0.52s |

Targets and the cluster's normal internet path are healthy. Only the VPN-pinned path is broken.

## Step 3 — What is the VPN path? (`scripts/002`)

`blackbox-exporter-vpn` gets a second interface via Multus:
`k8s.v1.cni.cncf.io/networks: network/vpn` → macvlan on node `eth1`, static `10.10.31.20/24`, gw `10.10.31.1`,
with ~31 split routes (`0.0.0.0/5`, `64.0.0.0/2`, …) forcing internet via that gateway.
Same pattern as `metube`, `sabnzbd`, `shelfmark`, `slskd`, `changedetection` (10.10.31.10–.17).

Caveat found the hard way: the cluster is **single-node**, so the pod→pod ping on `10.10.31.0/24`
(1.9ms, success) is in-kernel macvlan bridging and proves nothing about the physical uplink.

## Step 4 — Timeline (`scripts/003`)

- **2026-11-21 08:31:07 UTC** — both VPN probes go 0, **continuous since** (~26h, no flapping).
- 08:37 UTC — `up{instance="gateway.cloudjur.com:9100"}` drops: the **firewall itself went dark**.
- 09:50:45 UTC — gateway boot time (OPNsense rebooted).
- 10:03:01 / 10:04:42 UTC — second infra host and `k8s-0` boot.
- 10:05:01 UTC — blackbox-vpn container `exitCode 255 / reason Unknown` (node-level kill, not an app crash).
- 10:13 UTC — alertmanager `startsAt` (later than 08:31 because Prometheus itself restarted through the event).

So the outage **preceded** the reboot by ~1.5h and the reboot did not fix it. No GitOps commits landed
2026-11-19→23, so this was not a config change from the repo — it is an infra event (power/maintenance window).

## Step 5 — Is the VPN tunnel down? (`scripts/004`)

**No.** OPNsense exporter is unambiguous:

- `opnsense_wireguard_peer_status{peer_name="ProtonVPN_Singapore"}` = 1 (up)
- last handshake 67s ago (fresh)
- `opnsense_gateways_status{name="WAN_ProtonVPNSingapore"}` online, **loss 0%**, **RTT 14.1ms**
- CARP healthy: `carp_allowed=1`, `demotion=0`, `maintenance_mode=0` (so not an HA/VIP failover issue)

`vlan0.31.1` = interface **`VPN_SERVICES_LAN`**. Its counters collapsed the moment the probes died:
tx ~6000 B/s before 08:30 → 79 → 22 → 12 B/s after (probe trickle only). `wg2` tx fell to keepalive-only
(~136 B/s) while the tunnel stayed up. Traffic is dying before it reaches the tunnel.

## Step 6 — Where does it die? (`scripts/005`, `006`)

Blackbox `debug=1` trace from the VPN exporter:
- HTTP: DNS `resolve` = 0.010s (fine), **`connect` phase = 0s** → the syscall errored immediately, not a timeout.
- ICMP: `phase="rtt" 0` → request sent, no reply, ran out the 5s timeout.

Cluster DNS resolves, the pod has its routes, but the next hop `10.10.31.1` neither answers ICMP
(5.003s timeout) nor forwards anything. `opnsense_firewall_in_ipv4_block_packets{interface="vlan0.31.1"}`
≈ 40/hr against only ~1119/hr passed — that interface is being dropped at, not beyond.

Two concrete leads on the firewall, both things I could **not** confirm read-only from the cluster:

1. **CrowdSec is stopped** (`opnsense_services_status{name="crowdsec"} = 0`, 2 services stopped of 31).
   Its bouncer installs pf tables that survive a service stop *and* a reboot. A stale ban covering the
   VPN path would produce exactly this signature: tunnel up, nothing forwarded, counters blocking.
2. **`opnsense_firmware_needs_reboot = 1` and `opnsense_firmware_upgrade_needs_reboot = 1`** — pending
   packages plus a reboot-pending flag, consistent with firewall/policy-route state having come back
   incompletely after the 09:50Z reboot (policy route / outbound NAT for `VPN_SERVICES_LAN` → `WAN_ProtonVPNSingapore`).

## Impact — real, not cosmetic (`scripts/006`)

`slskd-0` (Soulseek, `media`) streamed >1kB/s for the first ~30h of a 3-day window and went flat at the
outage boundary, holding ~320 B/s (keepalive) since. `metube`/`sabnzbd`/`shelfmark` idle at ~110 B/s.
Every workload pinned to `10.10.31.0/24` has had no internet egress for ~26h.

## Conclusion

The alert is a **true positive and correctly scoped**. Root cause is **not** blackbox, not the Prometheus
stack, not the Proton tunnel: it is the OPNsense `VPN_SERVICES_LAN` (VLAN 31) egress path, broken since
2026-11-21 08:31 UTC during a firewall outage/reboot and still unrecovered. Fix belongs on the firewall,
starting with CrowdSec's bouncer state and the `VPN_SERVICES_LAN` → `WAN_ProtonVPNSingapore` policy route
+ outbound NAT.

---

# Day 2 (2026-11-23) — resolution pass

## Step 7 — Recheck: nothing self-healed (~50h)

```
BlackboxProbeFailed  1.1.1.1                  starts 2026-11-21T10:13:12Z
VpnProbeFailed       https://one.one.one.one   starts 2026-11-21T10:22:29Z
VpnProbeFailed       1.1.1.1                   starts 2026-11-21T10:22:59Z
BlackboxProbeFailed  https://one.one.one.one   starts 2026-11-21T10:12:42Z
```

Live: `10.10.31.1` still times out at 5.002s, `1.1.1.1` still times out. CrowdSec still `0`,
`opnsense_services_stopped_total` still `2`, `firmware_needs_reboot` still `1`, `wg2` handshake
111s ago (healthy), `vlan0.31.1` tx `11.78 B/s`, `wg2` tx `135 B/s`, ~41.7 blocked pkts/hr.
Firewall uptime 48.1h → no second reboot. Two new unrelated alerts appeared:
`LinuxNodeHighMemoryUsage`, `NodeMemoryHighUtilization`.

## Step 8 — Decisive: the firewall ARP table proves L2 is healthy

```
10.10.31.1    60:be:b4:05:0a:b9   VPN_SERVICES_LAN  vlan  expired=false   <- firewall's own VLAN MAC
10.10.31.10   b6:5c:36:8d:03:84   VPN_SERVICES_LAN  vlan  expired=false   <- slskd
10.10.31.20   da:23:25:78:a1:24   VPN_SERVICES_LAN  vlan  expired=false   <- blackbox-vpn
10.10.31.254  16:44:bb:a0:a4:29   VPN_SERVICES_LAN  vlan  expired=false
```

`10.10.31.20` matches the blackbox pod's annotation MAC `da:23:25:78:a1:24` exactly.
**ARP sits below pf**, so a fresh ARP entry means the pod's frames reach the firewall and the
firewall is *choosing* not to answer or forward. This permanently rules out macvlan, node `eth1`,
VLAN trunking, and interface-down.

## Step 9 — Why the reboot argument matters for the fix

pf loads its ruleset from config at boot. The firewall rebooted at 09:50Z and stayed broken, so:
- **"unapplied changes" is ruled out** — a boot flushes that state.
- The fault must live in **persistent state**: the config itself, or pf tables that reload at boot.

That is what elevates the CrowdSec hypothesis: a dead bouncer leaves its tables in place *and*
stops expiring decisions → a permanent blackhole. It explains healthy tunnel + working ARP +
no ping reply + no forwarding, from one cause.

## Actions taken

1. **`scripts/007-opnsense-vpn-diag.sh`** — read-only OPNsense diagnostic for the user to run over
   SSH. `sh -n` clean (no bash-isms; OPNsense has no bash). Audited: contains no `pfctl -F`/`-f`,
   no apply/restart/reload/filter_configure, no writes to `/conf/`. Section 2 (`pfctl -m`) is the
   CLI equivalent of Diagnostics → Rule Test and names the acting rule.
2. **PR #2593** — `fix/opnsense-firewall-alerting-gaps`, adds `OpnsenseFirewallUnreachable`
   (critical, 10m) and `OpnsenseServiceStopped` (warning, 30m) to the opnsense-exporter app.
   Validated: server-side dry-run against the live CRD, `kustomize build` renders, both PromQL
   return `success`, and **rule 1 backtests to first firing at 2026-11-21 08:33 UTC** — the first
   minute of this outage. Deliberately excluded a `opnsense_wireguard_peer_status == 0` alert:
   `wg1` home-WG peers sit at `0` legitimately when no client is connected.
3. Confirmed OPNsense config is **not** GitOps-managed (only `opnsense-backup` CronJob, `@daily`,
   XML to SMB `/tank/Backup/Apps/Opnsense`, ZFS-snapshotted). A pre/post 08:31Z snapshot diff is the
   fallback if Rule Test is inconclusive. This path is also undocumented in
   `docs/ai-context/NETWORKING.md` — a real reason triage took two days.

---

# Day 2 (2026-11-23) — Step 10: OPNsense REST API replaces the shell

User asked to try the OPNsense API. This overturned the working hypothesis, so the trail matters.

**Access.** The exporter's API key is admin-scoped and already in-cluster
(`observability/opnsense-exporter-secret`), and the backup CronJob proves the firewall API is
reachable from pods. Created `observability/opnsense-api-probe` (`curlimages/curl:8.23.0`, cached,
no SA token, non-root, `envFrom` the secret so the key never transits a terminal). Auth: HTTP 200
in 0.15s against `192.168.1.1`. Captured as `scripts/008-opnsense-api-triage.sh`.

**Two API traps found the hard way:**
1. `firewall/filter/get` returns `{"rules":{"rule":[]}}` — 0 rules — while the firewall log reports
   `rulenr` 145/167. It is an API artifact, not reality. Rules must be read from `config.xml`.
2. **`firewall/filter/apply` answers `200` to a GET and applies the ruleset.** Hit once during
   endpoint discovery. Re-applying an unchanged ruleset is idempotent and changed nothing (probes
   still failed, log unchanged) — but it was a mutation I did not intend, and it independently
   disproved "unapplied changes". Never status-probe mutation endpoints.

`core/backup/download/this` returns the **plaintext live config.xml** (312 KB) — the same call the
daily backup job makes. That plus `diagnostics/firewall/log` was enough to settle this.

## What the config proved

- Rule `5ad2f102` ("Allow routing through WAN protonvpn"): `opt3`, `source ProtonVPN_WG_VPN_Hosts`
  → `dest !Private_Network`, `gateway WAN_ProtonVPNSingapore`, `keep state`, enabled. This is rule 145.
- Outbound NAT: `mode=hybrid`, rule `source ProtonVPN_WG_VPN_Hosts` → `interface opt12` (= `wg2`),
  **enabled**.
- WG instance `ProtonVPN-ExitSingapore` = `instance 2` → `wg2`, `tunneladdress 10.2.0.2/32`,
  `disableroutes=1`, peer `149.50.211.164:51820`, allowed `0.0.0.0/0`, keepalive 25.
- Gateway `WAN_ProtonVPNSingapore`: enabled, `fargw=1`, monitored.
- **Every VPN rule and the NAT rule were last edited 2025-11-18/19; WG section persisted 2026-01-03.**
  Config is not the trigger. No binat/1:1, no static routes, `<hasync>` unconfigured.
- CrowdSec's four ban tables: `current_items=0`, zero block packets → **my leading hypothesis was wrong.**
  Stopped services are only `crowdsec` + `iperf`.

## The decisive experiment

24 probes from the VPN exporter at **`1.0.0.1`** (chosen because the gateway monitor never pings it,
so nothing else can be confused with our traffic). Log came back in matching pairs:

```
18:50:47 vlan0.31.1  match/pass  10.10.31.20 -> 1.0.0.1  icmp  rule=145
18:50:47 wg2         match/pass  10.2.0.2    -> 1.0.0.1  icmp  rule=110
18:50:23 vlan0.31.1  match/pass  10.10.31.20 -> 1.0.0.1  tcp:443  rule=145
18:50:23 wg2         match/pass  10.2.0.2    -> 1.0.0.1  tcp:443  rule=110
```

So: pf **passes** it, the policy route **is** applied (on `wg2`, never `pppoe0`), and outbound NAT
**is** applied (source → tunnel address). Nothing is blocked anywhere locally. And **zero** reply
entries exist. Corroborated by `vlan0.31.1`: 70 B/s pods→firewall vs **12 B/s** firewall→pods.

## Why "gateway online, 0% loss, 13 ms" misled us for two days

`<monitor/>` is **empty**, so OPNsense monitors `10.2.0.1` — Proton's end of the tunnel — not the
internet. Proof: `10.2.0.2 → 1.1.1.1` lines appear only paired with our 30s probes, never at the
~10s monitor cadence; and a `10.2.0.1` ping can't be logged anyway because floating rule #0 requires
`destination NOT opt12`. **A VPN gateway can report perfect health while forwarding nothing.**

## Conclusion

Every local component is verified good. Our packets leave through the tunnel with the correct source
address and the provider returns nothing, for 52h, surviving a firewall reboot and a ruleset
re-apply. Fault is at the **Proton end**. The pinned values are the fragility: literal server IP
`149.50.211.164` and hardcoded tunnel address `10.2.0.2/32`, unchanged since Jan 2026. Proton's
status page shows no Nov 20–22 incident but lists a **"Global ProtonVPN infrastructure upgrade
campaign, Aug 31 → Nov 30 2026"** replacing paid servers and deprecating previously downloaded
configs — the same window.

Not fully excluded: "replies arrive at `wg2` but die in state de-NAT" — needs `tcpdump`
(script 007 §8). Exotic, and would not have survived a reboot.

## Actions

1. `scripts/008-opnsense-api-triage.sh` + `results/007-opnsense-api-rule-trace.md`; `findings.md`
   corrected with an explicit retraction of the earlier "dies before reaching the tunnel" and
   CrowdSec/NAT theories.
2. **PR #2593 amended** (`24d31a34`): `OpnsenseServiceStopped` now
   `opnsense_services_status{name!~"iperf"} == 0` instead of `opnsense_services_stopped_total > 0`,
   because `iperf` is deliberately idle and a permanently-firing alert is an unread alert. Verified:
   exactly one series matches (`crowdsec`). PR body updated with the monitor-target lesson.
3. Debug pod deleted after use.

## Day 2 — 2026-11-24, "can you test my network speed?" (step 009)

Ask: measure the link, and see whether the outage is bandwidth-related.
`scripts/009-network-speed-check.sh` → `results/008-network-speed-history.md`.

**It is not bandwidth.** The cluster's own hourly speedtest shows **912 Mbps down / 521 Mbps up /
7 ms ping, median, stable from Nov 17 through Nov 24** — the link carried full gigabit-class
throughput straight through the outage. The repo's baseline comment (`# home is 300mbps` / `50mbps`)
is stale by 3x and 10x.

What the measurement actually found:

1. **The Mac's Wi-Fi is the slowdown**: `networkQuality` = 115 Mbps down / 255 up, idle latency
   217 ms, responsiveness Low (445 ms up / 630 ms down). Ping to the *LAN gateway* averages
   20 ms (max 54 ms) on a Wi-Fi 6 link reporting 1441 Mbps — RF/client side, not the ISP.
2. **Cloudflare is ~450 ms from everything** (1.1.1.1 and 1.0.0.1, from both wired cluster and
   Wi-Fi; TCP connect to :443 took 0.3–1.4 s). Google is 130–180 ms, the speedtest server 7 ms.
   So it is the ISP's path to Cloudflare. There is no direct-path Cloudflare baseline in
   Prometheus: the only internet ICMP series is the VPN-egress probe, dead since Nov 21.
3. **Bufferbloat demonstrated**: at ~50 % uplink utilisation (my own test traffic) the same
   cluster test read 132 ms instead of 7 ms. AQM (CAKE/fq_codel) on the WAN is worth enabling.
4. **Three pre-existing bugs in `speedtest-exporter/app/prometheusrule.yaml`** — the speed alerts
   compare bits/s to Mbps (`< 200`, `< 30`, need `200e6`/`30e6`) so they can never fire, and
   `SpeedtestExporterAbsent` uses `absent(up{...} == 1)` with `for: 75m` against a 60-minute scrape
   interval, so a vanished exporter never alerts either. Offered as a separate small PR, not yet
   opened.

Two readings were wrong before being corrected, both from the hourly scrape interval: `speedtest_*`
and `up` genuinely return "no data" for ~55 minutes of every hour. Use
`last_over_time(<metric>[2h])`; a raw `query_range` on the metric name is empty for the same reason.
Also: the exporter changes test server on its own (45623 → 912 Mbps, 70564 → 1.55 Mbps with 98 ms
jitter), so the history is not comparable across server changes.

Debug pod `observability/speed-probe` created and deleted; cluster left as found.

## Notable metric/API gotchas for next time

- Prometheus series key is `metric`, not `labels`. `query_range` needs absolute epochs.
- `node_network_receive_bytes_total`, not `..._received_...`.
- `curlimages/curl` has no `jq`/`python3` — copy the payload out and parse locally.
- `diagnostics/firewall/log` works as **GET** with `rowCount` capped ~1000 (~90s of traffic); the
  POST filter body returns 0 bytes.
- 404 here: `firewall/nat*`, `plugin/wireguard/*`, `core/service/status`, `diagnostics/state*`,
  `command_interface/run`. `diagnostics/ping/get` returns only the form model, it does not execute.
