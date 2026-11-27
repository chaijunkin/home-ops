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

## Day 2 — 2026-11-24, "not only Wi-Fi is slow, the exporter graph is slow too — gateway issue?" (step 010)

Ask: is OPNsense responsible for the slowness the user sees in the speedtest graph?
`scripts/010-opnsense-api-health-sweep.sh` → `results/009-opnsense-gateway-and-isp-path.md`.

**No. Traceroute hop 2 is the ISP's own gateway at 120-142 ms**
(`isdn-tsk-239-254.tm.net.my` = 210.186.239.254, Time dotCom), and every destination inherits it.
The firewall itself has no shaper at all (0 hits for shaper/limit/pipe/queue/altq/cake/fq_codel in
the live config), no static routes, pf states 1.2%, mbuf 2.9%, load1 avg 0.45, PPPoE stable,
upload still ~520 Mbps. Traffic never moved onto the WireGuard tunnel (peer RX flat at 0.5-0.7 kB/s
of handshakes). The Mac is not split-tunnelling.

But the firewall config has a real **blindness** fault: `/api/routes/gateway/status` shows
`WAN_PPPOE` with monitor/loss/delay all `~` — **gateway monitoring disabled** — reported as
"Online" because nothing checks it. The only monitored gateway pings Proton's tunnel end, and that
one went 13 ms -> 146 ms / 6% loss today, corroborating the same upstream congestion.

Timeline from the exporter's own log (local MYT): 20:28 = 6.8 ms / 912 Mbps on server 45623;
21:28 = 132 ms / 108 Mbps; **22:04 = same server 45623 at 121 ms / 162 Mbps** - which rules out
"the exporter just picked a bad server". Degradation began between 12:28 and 13:28 UTC.
Also: `?serverId=` is ignored by this exporter build (asked 45623, got 44364).

Three problems now cleanly separated: (1) ISP congestion, new and active; (2) OPNsense gateway
monitoring disabled -> no firewall-side visibility, ever; (3) the Nov 21 WireGuard egress failure,
still provider-side, plausibly the same operator.

### Working-tree wipe and recovery (important)

At 22:45 MYT a `git reset --hard` + clean dropped two commits off `fix/scope-opnsense-service-alert`,
including the committed investigation log. Both were recovered from dangling commits: tagged
`recover/investigation-log-20261124` (a18af682b) and `recover/docs-curation-20261124` (1d03b575f),
archived to the temp dir, and `docs/investigations/` restored **unstaged** with
`git archive ... | tar -x` so it stays out of the PR. `1d03b575f` is not mine (APP_KNOWLEDGE
curation) and still needs re-landing by its author.

## Day 3 — 2026-11-25, "why is my speed so unstable? troubleshoot at OPNsense gateway level" (steps 011-012)

`scripts/011-gateway-level-stability.sh` + `scripts/012-gateway-config-audit.sh`
→ `results/010-gateway-audit-and-isp-loss.md`.

**Cause: ~12.5% packet loss and 135 ms at Time dotCom's own gateway address**
(`210.186.239.254` / `isdn-tsk-239-254.tm.net.my`), measured 30 probes/hop:
LAN `192.168.1.1` 0.0% loss 3 ms -> BRAS **12.5% loss 135 ms** -> `8.8.8.8` **12.5% loss 149 ms**.
Loss that heavy is exactly why the speed test swings between 940 Mbps and 2.5 Mbps: TCP keeps
closing its window. Not a cap, and not test-server luck - 940/916 Mbps were achieved at 114-130 ms
RTT on two different servers.

dpinger (the only monitored gateway) shows **two episodes**: 24 Nov 13:00-15:30Z at 129-147 ms /
10-18% loss, then **~11 h completely clean at 13-20 ms**, then from 25 Nov 06:00Z onward
125-159 ms / 0-10% loss, still active. Exporter log in MYT matches: clean until 13:28, degraded
from 14:28 with download 940 / 2.48 / 916 / 4.98 / 36 Mbps while upload held 455-623.

**Gateway config audit - nothing in OPNsense causes it, but four things need fixing:**
`WAN_PPPOE.monitor_disable=1` (the internet gateway is never checked -> firewall blind);
latency/loss thresholds empty (defaults ~500 ms/20% would not alarm at 135 ms/12%);
`monitor_killstates=0` everywhere (states stay pinned to a dead gateway, which is why the Nov 21
VPN failure is sticky); zero `<mss>` in the whole config (PPPoE 1492 + WireGuard 1420 will
black-hole large packets once the tunnel works again). Plus a dead leftover gateway `Wireguaurd`
(disabled, empty gateway address).

**Explicitly ruled out, with numbers:** 0 gateway groups/pools (no failover flapping), 0 policy
routes, no CARP VIP, no shaper/altq/dnshaper, 0 input/output errors on every NIC over 6 h, no
PPPoE counter resets, pf states 1.3%, mbuf 2.9%, CPU peak 27.2% / load1 1.40, path-MTU 64->1464 B
answered with no blackhole, only 3 sysctl overrides (benign). All checksum/TSO/LRO offloads are
disabled (costs CPU, not the bottleneck at 27%). CPU 79-84 C sustained, 87 C peak - warm, not
throttling.

Ticket text for Time dotCom is in `results/010-...md`, including the correlation with the Nov 21
incident.

### Gotchas learned
- `date '+%H:%M %Z'` twice does not give UTC; use `date -u`. The exporter logs are TZ=MYT (UTC+8),
  so every timestamp needs converting before comparing with Prometheus.
- `max_over_time(1 - avg(rate(...))[24h:1m])` is invalid; the expression inside a subquery must be
  parenthesised.
- Range queries on hourly metrics still miss samples depending on step anchoring; for this
  exporter the pod's own log lines are the authoritative history.

## Day 3 — 2026-11-25, "is it the ISP, my services, or a device hogging the network?" (step 013)

`scripts/013-why-is-everything-slow.sh` (+ `scripts/lib-fmt.py`) → `results/011-isp-not-home-devices.md`.

**Answer: the ISP. Nothing at home is hogging it.** The link was **94 % idle while unusable**:
5.6 Mbps of ~912 Mbps in use now, **peak 5-min rate in 12 h = 58.2 Mbps**, total 38.7 GB down /
18.6 GB up over 12 h. Busiest internal segment peaked 55 Mbps, `vlan0.31.1` ~0. So self-inflicted
congestion is arithmetically excluded - and 62.5 % ping loss cannot come from 0.6 % utilisation.

Loss location, Wi-Fi (30 probes): `192.168.1.1` **0.0 %**/14 ms -> BRAS `210.186.239.254`
**37.5 %**/145 ms -> `8.8.8.8` **62.5 %**/150 ms -> `1.1.1.1` **25 %**/176 ms.
Same Wi-Fi path is clean to the firewall, so loss starts past it. Wired confirmation (TCP only,
no ICMP, no Wi-Fi, from a cluster pod): handshakes **139-181 ms, worst 1.2-3.2 s** vs 5-7 ms on
24 Nov. Real downloads **2-3 Mbps** wired, **12 Mbps / timeout / 23 Mbps** on Wi-Fi, while upload
holds **518 Mbps**. macOS `networkQuality`: idle latency **436 ms**, downlink responsiveness
**707 ms (Low)**. Exporter 19:28 MYT: **Download 1.03 Mbps / Upload 518 Mbps / Ping 147.7 ms**.

**Retraction:** the multipath-spraying idea I raised mid-step is wrong. 60-probe sorted RTTs are
unimodal (135-157 / 145-173 / 163-182 ms), 0 out-of-order arrivals, missing seqs never reappear.
Genuine loss on one degraded path, and worsening: 12.5 % loss at 19:15 -> 37.5 %/62.5 % at 19:37.

DNS is not implicated (3-8 ms lookups). An updated, much stronger ISP ticket is at the end of
`results/011-isp-not-home-devices.md`.

## Day 3 — 2026-11-25, "what can I do? did you check the GUI, API config, live log or traffic?" (steps 014-015)

`scripts/014-opnsense-live-log-and-traffic.sh` + `scripts/015-loss-recorder.sh`
→ `results/012-opnsense-log-and-traffic-coverage.md`.

**Honest coverage answer:** the GUI was never used (no credentials, I don't drive the web UI).
API **config** = fully (live 312,402-byte config.xml). API **gateway runtime state** = yes
(dpinger, repeatedly). **Live firewall log** = only now: `GET /api/diagnostics/firewall/log`
returned 1000 rows over 95 s -> **936 pass / 64 block, all rule 13 "Default deny / state
violation"**. Zero blocks of outbound or return traffic, so the firewall is definitively not
dropping anything. The 8 WAN blocks are inbound internet scanning to the public IP
**210.186.239.63** (normal). The 56 `vlan0.32.1` blocks are `10.10.32.2/.3/.4/.5 ->
16.163.195.33:9999` + NTP -> an unrelated VLAN-32 policy gap worth fixing.
**Per-connection views are not available with this key**: getStatesSummary / getStateCount / dump /
firewall/statistics/show / getInterfaceTraffic / getInterfaceRates / getARPTable / getSystemInfo
are all 404, and there is **no NetFlow plugin**, so no per-flow history exists. System/PPP logs
return HTTP 200 with body `[]` on GET (the GUI reads them via POST), so link-event logs remain
unread - check Status -> System Logs -> PPP in the GUI, or approve a read-only POST probe.

**New decisive measurement** (`015-loss-recorder.sh`, 8 rounds, 12 s apart, 20:20-20:24 MYT):
LAN `192.168.1.1` = **0.0 % loss in every single round, ~4-5 ms**, while the ISP's own gateway
`210.186.239.254` answers in **136-152 ms constantly (avg 141.7 ms) even in rounds with 0 % loss**;
public loss bursts to 66.7 %; real downloads **2.3-15.6 Mbps**.
Key insight: **latency is steady, loss is bursty.** The ISP's CPE-facing gateway should reply in
1-5 ms; 140 ms there is physically impossible to cause from inside the house. Points at access /
aggregation (ONT optics, flapping uplink, congested BRAS), not at a queue my traffic created.

`015-loss-recorder.sh` is now the tool to run live during the ISP call (SAMPLES/INTERVAL/CSV are
env-tunable) - it prints a timestamped LAN-vs-ISP table plus a real download figure.

## Day 4 — 2026-11-26, "how to resolve the VPN alert probe issue?" (steps 016-021)

`scripts/016-vpn-probe-state.sh`, `017-vpn-egress-layer-probe.sh`, `018-vlan31-egress-ip-test.sh`,
`019-mss-sweep.py`, `020-handshake-reality-check.py`, `021-firewall-log-with-known-traffic.sh`
→ `results/013-vpn-resolution-plan.md`.

**The ISP recovered (hop 2 back to 13 ms / 0 % loss) but VpnProbeFailed is still firing**, so the
VPN fault is now cleanly isolated from the ISP fault. Four known flows were generated from
`10.10.31.15` and each appears **twice** in the live pf log: `vlan0.31.1` rule **145** with the pod
source, then `wg2` rule **110** with source **`10.2.0.2`** - policy routing and outbound NAT are
both correct. **Zero return rows on any interface.** Meanwhile dpinger reaches Proton's tunnel end
`10.2.0.1` at 13 ms / 0 % loss and wg2 keeps exchanging 0.6 kB/s of handshakes, so crypto,
reachability and keying all work. Conclusion: **Proton accepts our packets into the tunnel and
forwards nothing back.** Provider-side, unchanged since 2026-11-21 08:31Z.

Hypotheses killed with measurements, not assumption:
- **MTU/PMTUD** - I thought this was it (wg2 MTU unset = 1500 over PPPoE 1492, zero `<mss>` in the
  config). MSS sweep 1460/1452/1440/1436/1420/1400/1380/1360/1340/1280/1220/**1000** -> **all 12
  fail** with `SSL: UNEXPECTED_EOF_WHILE_READING`. Wrong. Retract.
- TLS-specific - plain HTTP also times out. No.
- DNS - `api.ipify.org` resolved to 172.67.74.152 and was logged on wg2. No.
- "traffic leaks via WAN instead of Proton" - searched every new pppoe0 row for 10.10.31/10.2.0
  sources: none. No.
- closed ports (12345/8701/9999) "connecting in 13 ms" in the first pass: on repeat they time out,
  and pf shows only outbound. **`tcp_connect` is not a usable health signal on this path.**

Fix = Proton side: (1) repoint the peer off the hard-coded `149.50.211.164:51820` (pinned since
Jan 2026) to a different Singapore server via VPN > WireGuard > Instances > Peers; (2) two-minute
split test - Proton app on a phone **on mobile data**: app works -> our pinned endpoint; app fails
too -> Proton ticket (text is in results/013); (3) rotate the WG keypair if a new server also fails.

Alerting is also wrong and needs its own PR: `vpn-icmp -> 1.1.1.1` can **never** pass (Proton does
not forward client ICMP) and `tcp_connect` reports success during a total outage, so the only
trustworthy probe is `http_2xx`. Add **`VpnTunnelUpButNoReturn`** (tx on wg2 > 0 while rx < 1 kB/s
for 30 m - the exact signature of this incident, which nothing caught) and
**`VpnEgressLeakingToWAN`** (VLAN-31 public IP not in Proton ranges - the silent un-proxy risk),
plus the three dead speedtest rules and the two gateway-monitoring alerts. PR #2594 still unmerged.

## Day 4b — 2026-11-26, re-measuring speed after the ISP recovered + two retractions (step 022)

`scripts/022-sustained-load-ladder.sh` -> `results/014-post-recovery-speed-and-cap.md`.

**The 25 Nov access-path impairment is gone.** ISP gateway `210.186.239.254` now answers in
**8-9 ms with 0 % loss** (was 136-152 ms, up to 37.5 %), `8.8.8.8` 14-15 ms / 0 %. What remains is a
**throughput shortfall with clean latency**: 3 concurrent 60 MB downloads = **566 Mbps** vs the 912
baseline (62 %), 2 concurrent uploads = **344 Mbps** vs 521 (66 %). Fast RTT + zero loss + a lower
ceiling is the signature of a **rate cap or a re-homed PPPoE session**, not congestion - the WAN
re-dialled at ~10:21 MYT on 25 Nov, so the circuit may have landed on a different LNS/profile.
Worth asking Time dotCom for the assigned LNS and profile rate-limit.

**Two errors of mine, both found and corrected (recording them because both could have become
fake conclusions):**
1. `speed.cloudflare.com/__down?bytes=100000000` returns **HTTP 403** - the endpoint caps `bytes`
   just under 100 MB. `bytes=99000000` gives 200 at 387 Mbps. So the "downloads stall to 0 Mbps"
   rows in the ladder are a **test artifact**. The 25 Nov conclusion stands because those samples
   used 2-8 MB requests that completed at 2-16 Mbps. Cross-checked with
   `proof.ovh.net/files/100Mb.dat` -> 200, 95 Mbps (far server).
2. My parallel-run summariser printed "SUM = 0 Mbps" for a healthy test: `curl -w` writes
   `  stream1: 30773633` and the summariser did `float(entire file)`. Re-parsed: 246+107+213 = 566.

**Third correction, from reading config.xml instead of inferring:** `wg2` is **not** MTU 1500 - the
WireGuard instance `ProtonVPN-ExitSingapore` sets `mtu=1420` (the interface-level `<mtu>` is empty).
1420+60 = 1480 <= 1492 PPPoE, so the arithmetic is fine and the hygiene note in results/013 is
weaker than I wrote: MSS clamping is still worth doing, but "set wg2 MTU 1420" is already done.
Also confirmed literally: peer `ProtonVPN_Singapore` -> `serveraddress 149.50.211.164:51820`,
`tunneladdress 0.0.0.0/0`, `keepalive 25`; instance `tunneladdress 10.2.0.2/32`, `disableroutes 1`,
`dns 10.2.0.1`. And `wg1`/`Home_Wireguard` is an **ingress-only** server (`ddns.cloudjur.com:51820`,
10.10.29.1/24) - it cannot take over as an exit, so there is genuinely no failover target.

**My mistake, disclosed:** while consolidating the gateway audit I overwrote
`results/010-gateway-audit-and-isp-loss.md`, which already existed from 25 Nov and held the original
hop-by-hop table and the first Time dotCom ticket text. The numbers are restored into that file from
this chat log, and the **ticket text is safe in `results/011`**, whose version already superseded it.
Nothing in git (docs/investigations is untracked by design), so treat this as a lesson: `read`
before `write` on numbered files, because the numbering scheme guarantees collisions when a step is
re-run - which is also why today's script had to be renumbered 013 -> **022**.

**Control test still owed by the user:** the Proton app on this Mac is currently **disconnected**
(`utun7` has no inet address, `api.ipify.org` returns the home IP `210.186.239.63`, and
`https://1.1.1.1` answers HTTP 301 in 0.08 s directly). So it proves nothing yet - connect it and
re-run the egress check.

## Day 4c — 2026-11-26, ICMP retraction + an alert expression that is actually proven

Compared `vpn-icmp` and `vpn-http` hour-by-hour for 20 days. **My 25 Nov claim that
"`vpn-icmp -> 1.1.1.1` can never pass, Proton does not forward client ICMP" is wrong.** ICMP was
green every day 11-20 Nov. Over 20 days of hourly samples: both-down 111, icmp-down-only 2,
http-down-only 0 - the two probes agree essentially always and neither false-alarms. **Keep both.**
What that table really bought us is the outage boundary: first failed sample **2026-11-21 16:00 MYT
(08:00 UTC), still failing 26 Nov - five continuous days**, not the flapping a 48 h window suggested.
The probe-design problem is the opposite one: `tcp_connect` lies on this path, so it must never be
added as a tie-breaker.

Designed and **validated** the missing alert against real history. Two traps found while testing:
1. `(<handshake expr>) and (<probe expr> == 0)` returned **zero series even though both halves
   matched** - the wg metric (`instance=10.69.0.68:8080, job=opnsense-exporter`) and the probe metric
   (`job=probe/observability/vpn-*`) share no labels, so `and` matches nothing. Needs `and on()`.
2. Unscoped, it fires forever on the inbound-only `wg1` peers, whose
   `opnsense_wireguard_peer_last_handshake_seconds` is `0`. Must scope
   `device="wg2", peer_name="ProtonVPN_Singapore"`.

Final form, with live results: quiet 13/20 Nov, fires 23 Nov (handshake_age 131 s), 25 Nov (93 s),
and now (127 s). I preferred this over a throughput threshold because the peer counters separate the
states ~100x (healthy `rate(opnsense_wireguard_peer_received_bytes_total{device="wg2"})*8/1e3` =
**40.6-58.0 kB/s**, outage = **0.5-0.7 kB/s**) - but any fixed threshold would false-positive when
the tunnel is legitimately idle, whereas handshake-freshness + probe-failure needs no threshold.

Artifacts: `scripts/022-sustained-load-ladder.sh` (renumbered from a colliding 013),
`results/014-post-recovery-speed-and-cap.md`, corrected `results/010` (was overwritten by me, see
Day 4b) and `results/013` (ICMP retraction + validated rule).

## Day 4d — 2026-11-26, and then I contradicted myself about the speed, twice

I wrote above that throughput was stuck at **62-66 % of baseline** and inferred a rate cap or a
re-homed PPPoE session. **That was wrong.** The in-cluster speedtest exporter, hourly and unattended,
logged **910-922 Mbps down / 521 Mbps up at 5.7-11 ms ping** for every hour from 00:28 to 08:28 MYT,
after showing the real fault at 22:28 (2.23 Mbps, 231.98 ms ping). The circuit recovered fully between
23:28 and 00:28 MYT and is at baseline.

Four of my own errors, all in one morning, each one capable of becoming a fake conclusion:
1. **Vantage.** All my "speed" numbers came from the Mac on **Wi-Fi** (334-387 Mbps single stream,
   566 Mbps x3). The wired exporter gets 910-922 Mbps at the same instant. The gap was Wi-Fi.
2. **Double unit conversion.** `speedtest_download_bits_per_second` is already bit/s, so 916540000
   *is* 916.54 Mbps; I multiplied by 8 again and printed "7332 Mbps". Same class of bug as the
   rules' dead thresholds (`< 200`, `< 30` comparing bit/s against Mbps) -> fix is `200e6`/`30e6`.
3. **Endpoint artifact.** `speed.cloudflare.com/__down?bytes=100000000` returns **HTTP 403** (capped
   just under 100 MB); `bytes=99000000` gives 200 at 387 Mbps. So "stalled to 0 Mbps, 1 byte" was the
   CDN refusing the request. 25 Nov numbers stand (2-8 MB requests).
4. **My parser.** `curl -w` writes `  stream1: 30773633`; I did `float(whole file)` and reported a
   healthy run as "SUM = 0 Mbps".

Also corrected: I had recorded that `SpeedtestExporterAbsent` "can never fire". It is **fine** - the
exporter is scraped hourly (`interval: 60m`), so instant queries show "no data" ~55 min of every
hour, and `for: 75m` is deliberately longer than the scrape interval. It fires when 75 consecutive
minutes pass with no good scrape, which is the intent. Only the two threshold rules are truly dead,
so the PR fixes those two and leaves the absent rule alone.

Practical takeaway for this repo's alerting: **the exporter is the authority on circuit speed**, and
`speedtest_*` needs `last_over_time(m[2h])` (or the pod log) for any "right now" question.

## Day 4e — 2026-11-26, opened the alerting PR + one more correction of mine

Built and validated the alerting change set on `fix/vpn-egress-and-gateway-alerting` (off
`origin/main` = `06e749a2d`), four files, no cluster or firewall mutation:

| file | change |
|---|---|
| `opnsense-exporter/app/prometheusrule-gateway.yaml` (new) | `OpnsenseGatewayMonitoringDisabled` (`opnsense_gateways_monitor_info == 0`), `OpnsenseGatewayDegraded` (RTT > 60 ms for 30 m) |
| `opnsense-exporter/app/kustomization.yaml` | register the new file (sorts before `prometheusrule.yaml`) |
| `blackbox-exporter/vpn/helmrelease.yaml` | `VpnTunnelUpButNoReturn` |
| `speedtest-exporter/app/prometheusrule.yaml` | `< 200` -> `< 200e6`, `< 30` -> `< 30e6`, `Mbps` -> `bit/s` in the descriptions |

A **separate rule file** for the gateway alerts is deliberate: PR #2594 edits the same
`prometheusrule.yaml` hunk region, and the repo already has precedent (`prometheusrule-linux-node.yaml`).

Every expression was evaluated against live Prometheus at historical instants, not reasoned about:

- `VpnTunnelUpButNoReturn` — quiet 13/20 Nov; fires 23 Nov (handshake age 131 s), 25 Nov (93 s), now
  (144 s). Tested two right-hand forms: bare `probe_success == 0` and `max(probe_success) == 0`.
  Both behave identically with no Prometheus warnings; **shipped the aggregated one** so the alert
  means "every VPN probe failed", keeping one flaking endpoint from impersonating a provider fault.
- `opnsense_gateways_monitor_info == 0` -> fires for `WAN_PPPOE` only. Reading the firewall's own
  flag beats inferring "no RTT series", which would also match the disabled `Wireguaurd` leftover.
- `OpnsenseGatewayDegraded` (RTT > 60) -> quiet 13/20 Nov, fires through 24-25 Nov.
- Corrected speedtest threshold proven on real samples: at the 25 Nov 22:28 failure sample
  (2.23 Mbps = `2.227e6` bit/s) `... < 200e6` **fires** and the old `< 200` is **quiet**. That is the
  cleanest possible proof the old rule was dead.

**Correction to what I wrote on 25 Nov:** I claimed WAN monitoring being off is "why *nothing*
alerted during this whole incident". Overstated. `SpeedtestHighPingLatency` and
`SpeedtestHighJitterLatency` did fire for the 24-25 Nov episode - 4 h averages of **154.6 ms** and
**181.7 ms** at 25 Nov 23:28 MYT, quiet today at ~7 ms. The accurate claim is that the **gateway
layer** had no signal: dpinger ran nothing for the WAN, so the firewall never marked it down and
never killed dead states. `results/010` now says that, and adds the dpinger series that backs the
whole design argument: `opnsense_gateways_rtt_milliseconds{name="WAN_ProtonVPNSingapore"}` held
**12.8-24.7 ms through 21-23 Nov, the entire non-forwarding outage**, and only inflated to 125-160 ms
on 24-25 Nov when the ISP path itself degraded. Gateway monitoring structurally cannot see a provider
that handshakes and forwards nothing - hence `VpnTunnelUpButNoReturn`.

**Validation-tooling facts worth keeping (each cost me a wrong "it passed"/"it failed"):**
1. `scripts/kubeconform.sh` takes the **`kubernetes` root**, not an app subtree - it starts with
   `find "$1/flux"`, so pointing it at `kubernetes/apps/observability/exporters` dies on a missing
   `flux` dir with `EXIT=1` having validated nothing.
2. `pre-commit` runs **prettier on every yaml**, so hand-formatted manifests must be prettier-clean
   or the commit gets rewritten under you. It reformatted my speedtest edit (folded the `summary`
   plain scalars); semantics unchanged, verified by re-reading the diff.
3. Block-scalar style in this repo's rules is `|-`, not `|`; matched the sibling file.
4. System `python3` here has **no `yaml` module**, and `promtool` is not installed - so "does the
   YAML parse" is best answered by `kustomize build` (which also proves the new resource is wired
   into the kustomization) plus prettier.
5. zsh again: unquoted `$FILES` is **not** word-split, so `prettier --check $FILES` reported
   "No files matching the pattern" while still printing "All matched files use Prettier code style" -
   a green-looking result from a command that checked nothing. Same class of bug as the 4d parser.

## Day 4f — 2026-11-26, PR #2604 opened, and a doc-consistency sweep

**PR #2604** is open: <https://github.com/chaijunkin/home-ops/pull/2604>
(`fix/vpn-egress-and-gateway-alerting`, commit `a48917e09`, 4 files, alerting manifests only).

Evidence gathered for the record, all read-only:
- `task kubernetes:kubeconform` -> `EXIT=0`, with `PrometheusRule opnsense-exporter-gateway-rules`,
  `PrometheusRule opnsense-exporter-rules`, `PrometheusRule speedtest-exporter-rules` and
  `HelmRelease blackbox-exporter-vpn` each reported valid.
- `prettier --check` clean on all four files; `kustomize build` renders both `PrometheusRule`s.
- CI on the PR: `Labeler pass`, `Image Pull - Extract Images pending` at the time of writing.
- **PR #2594 merged while I was working** (`05e4eec7d`, 2026-11-26T01:40Z). My "still open, please
  merge" was read before the merge; re-checked rather than left as stated.
- Cleanup done: deleted my bare scratch pod `opnsense-read` from `observability` (verified no
  ownerRefs first, so nothing manages it and no GitOps drift results) and stopped all port-forwards.

**Swept every results/ file for claims I had retracted but left written down.** Three contradictions
found and fixed, because a stale conclusion in a runbook is worse than no runbook:
1. `results/013` said `SpeedtestExporterAbsent` "must use `absent_over_time`, `absent(up{...} == 1)`
   on an hourly scrape can never fire" -> retracted; `for: 75m` vs `interval: 60m` is correct and
   `absent_over_time` would only make it twitchier.
2. `results/013` recommended "add a second independent HTTP target" -> **reversed**. `VpnProbeFailed`
   keys on `service="blackbox-exporter-vpn"`, so a new target under that label couples VPN alerting to
   a third-party endpoint's health. The shipped rule instead requires *all* probes to fail
   (`max(probe_success{...}) == 0`), which gets the same safety without a new dependency.
3. `results/013` planned a `runbook_url` annotation -> deliberately skipped: `docs/investigations/` is
   untracked by design, so it would be a dead link for whoever the alert pages.

Also corrected in `results/010`: my "nothing alerted during this whole incident" was overstated (the
speedtest ping/jitter alerts did fire on 24-25 Nov); the precise claim is that the **gateway layer**
had no signal, plus the new dpinger evidence that the VPN gateway held 12.8-24.7 ms straight through
the 21-23 Nov outage and only inflated when the ISP path itself degraded.

**Still owed by the user (nothing I can do read-only):** the 2-minute Proton control test on mobile
data, repointing the pinned peer off `149.50.211.164:51820`, merging #2594 and #2604, restarting
CrowdSec, and the four firewall settings (WAN monitoring on, VPN monitor IP -> `1.1.1.1`, delete the
dead `Wireguaurd` gateway, MSS clamp 1360).

## Day 4g — 2026-11-26, "what else is missing?" -> audited all 77 rules

`scripts/023-alerting-coverage-audit.py` + `scripts/024-dead-rule-forensics.py`
-> `results/016-alerting-coverage-gaps.md` (raw dumps: `results/016-alerting-coverage-gaps-raw.txt`,
`results/017-dead-rule-forensics.txt`).

Method rather than opinion: extract every `expr:` under `kubernetes/apps`, diff against the 4 856
live metric names, then classify each hit as my-regex-false-positive / renamed-metric / exporter-not-
running. **17 of 77 rules reference names that do not exist**, of which **6 groups are real** and
protection advertised by them does not exist:

1. **smartctl - 7 rules, zero `smart*` metrics**, exporter commented out at
   `exporters/kustomization.yaml:7` -> **no disk-health alerting at all**.
2. **volsync - `volsync_volume_out_of_sync` does not exist**, no `volsync_*` family -> backup
   replication drift unalerted, in a repo whose own alertmanager config documents 10 failed snapshots.
3. **cloudflared** `cloudflared_tunnel_user_connections` -> renamed to `cloudflared_tunnel_ha_connections`.
4. **autobrr** `autobrr_irc_channel_monitored_total` -> `autobrr_irc_enabled_total` / `_healthy_total`.
5. **dragonfly** `dragonfly_used_memory_bytes` / `_limit_bytes` -> `dragonfly_memory_used_bytes` / `_max_bytes`.
6. **litellm** `litellm_deployment_(failed|successful)_fallbacks_total` not exposed -> the two
   failover alerts are dead (the latency/failure-rate ones in that file are fine and one is firing).

False positives from my own regex, recorded so nobody chases them: `requested_model`,
`exception_class`, `exception_status`, `fallback_model`, `exported_namespace` are **labels** in
`by ()`/matchers; `litellm_llm_api_latency_metric` is a histogram so a bare-name query shows "no
series" while `_bucket/_count/_sum` are live. `litellm_model_name` still needs a manual check.

**The structural lesson:** a missing series never equals `0`, so every threshold rule goes blind when
its exporter disappears - and smartctl/volsync are that bug in the wild, absent with zero alerts.
Coverage-presence alerting exists in exactly one place (`OpnsenseFirewallUnreachable`). Unalerted
helpers that make a cheap version possible: `opnsense_exporter_endpoint_errors_total`, and the
`opnsense_firewall_*_{block,pass}_packets` / `opnsense_firmware_*needs_reboot` families.

**The uncomfortable one:** delivery is healthy (2 327 notifications sent in 7 d, 1 failed; critical ->
Discord **and** Pushover). So `VpnProbeFailed` paged for five days and the incident still ran to
completion. Detection was not the failure. Missing: ack/escalation for an unhandled critical, and a
quieter baseline - 32 alerts fire right now (`KubeHpaMaxedOut` x22, `KubeJobFailed` x4 =
`ai-inference-smoke-test` x3 + a renovate discovery job, two overlapping memory rules), so a new
critical is one more red line.

Also still uncovered, restated with the data that makes each one safe to write: egress-identity leak
alert; `time() - opnsense_wireguard_peer_last_handshake_seconds > 300` scoped to the exit peer
(`wg1` peers sit at epoch 0 forever and would page forever); VLAN-32 egress (no probe on that path).

## Day 4h — 2026-11-26, #2604 merged, and a regression in #2594 (steps 026-032, PR #2607)

Ask was "continue, we dont use volsync anymore", following the coverage audit. Two things had to be
established before touching any rule file: what volsync's retirement actually leaves behind, and
which of my "dead rules" are deployed at all.

**#2604 is MERGED** (`0a90c2e8d`) and live: `VpnTunnelUpButNoReturn` is **firing right now**, which is
the first time this outage has been described by an alert instead of by me. `OpnsenseGatewayMonitoringDisabled`
is also firing — WAN_PPPOE monitoring is still disabled, so that to-do is still open. Also re-checked
my own scare of the hour: I queried `opnsense_gateway_status` (singular), found it missing, and nearly
called #2604 broken. The PR uses `opnsense_gateways_*`, which exists. My typo, not the PR's bug.

**Deployed-vs-absent matrix (`scripts/026`, `027` → `results/019`, `020`).** The audit had never asked
whether a flagged file is loaded, and that distinction changes the response entirely:

- `smartctl-exporter` and `volsync` rule files → **0 loaded rules each**. Obsolete config, not a gap.
  Volsync is fully retired: `apps/volsync-system/kustomization.yaml` comments out all three ks.yaml
  entries, 0 PVCs carry kopia/volsync annotations, CRDs linger as leftovers. **Do not** remove
  `snapshot-controller` with it — it runs in `kube-system` (1/1, 116 d) and kopiur's local-tier
  snapshots need it. Retracted: "backup drift has no alert" — kopiur ships 13 healthy rules over 79
  snapshot policies, newest backup 14.4 h old.
- Four loaded rule groups genuinely could never fire → fixed in **#2607**.

**The regression, which is the interesting finding (`scripts/029`, `030` → `results/029`, `030`).**
`OpnsenseServiceStopped` (#2594, mine, merged) had been **unable to fire since it deployed**. Not
because of a bad metric name — the metric exists and the condition is true — but because
`opnsense_services_status{name="crowdsec"}` reports `1` for one scrape every ~15 minutes while the
service has actually been stopped the whole time: 330 zeros and 31 ones across 361 one-minute samples
over 6 h, 62 transitions. Every one of those ones resets the `for: 30m` pending timer. ALERTS shows
`firing` until 01:40 (pre-#2594 rule on the label-less counter) and `pending` from 01:41 onward, with
`activeAt` marching forward and never converting. So a scoped rule that looks perfectly healthy in the
UI produced **five more hours of silence on a dead IPS**. Fix: `min_over_time(...[10m]) == 0` with
`for: 15m` — verified continuous over 45 m (46/46 samples), still excludes all 29 running services and
`iperf`. Generalised lesson: *a flapping input needs a look-back window; `for:` alone guarantees it
never fires.*

Corollary for crowdsec itself: restarting it is probably not the whole story. If the firewall flips it
to "running" every 15 minutes, it looks like something is repeatedly starting and killing it — worth
looking at Services → CrowdSec logs rather than assuming the restart fixed it.

**#2607 — what shipped** (`fix/unfireable-alert-rules-and-monitoring-coverage`):
`CloudflareTunnelOffline` → `cloudflared_tunnel_ha_connections`; `DragonflyHighMemoryUsage` →
`dragonfly_memory_used_bytes`/`_max_bytes`; `AutobrrNetworkUnmonitored` →
`autobrr_irc_enabled_total > autobrr_irc_healthy_total` (plus dropping the `{{ $labels.network }}`
template — those counters have no such label); LiteLLM's two `*_fallbacks_total` rules re-expressed
from `litellm_deployment_{failure,success}_responses_total` with `unless on (model_group)` so a missing
success series counts as "nothing works"; the `OpnsenseServiceStopped` look-back; and a new
`prometheusrule-monitoring-coverage.yaml` with `OpnsenseApiExporterAbsent`,
`OpnsenseExporterEndpointErrors`, `VpnEgressProbesAbsent`, `VpnEgressTunnelAbsent`.

Gate before pushing: every one of the nine expressions evaluated against live Prometheus (all return
no series today = correct), *and* each renamed one proven matchable by relaxing the comparison — quiet
for the right reason, not blind. `task kubernetes:kubeconform` exit 0 / 229 dirs / 1135 resources /
0 invalid with all five changed `PrometheusRule`s named valid; `kustomize build` rc=0 for all five
trees; `prettier --check` clean.

**Also learned the hard way this hour:** my earlier `task kubernetes:kubeconform ... | tail -12` gave
EXIT=0 from `tail`, and only 12 lines of log, so it proved nothing about coverage. Re-ran with full
capture and verified the changed directories appear. And `docs/investigations/` is now **tracked** on
main (`19c81cfa7`, committed 24 Nov), which is why switching branches aborted: main had 293 lines of
`chat.md`, my working copy 709. Backed up, removed the colliding files, checked out, restored the
longer log — and my old assumption "this folder stays untracked" is retired.

## Notable metric/API gotchas for next time

- Prometheus series key is `metric`, not `labels`. `query_range` needs absolute epochs.
- `node_network_receive_bytes_total`, not `..._received_...`.
- `curlimages/curl` has no `jq`/`python3` — copy the payload out and parse locally.
- `diagnostics/firewall/log` works as **GET** with `rowCount` capped ~1000 (~90s of traffic); the
  POST filter body returns 0 bytes.
- 404 here: `firewall/nat*`, `plugin/wireguard/*`, `core/service/status`, `diagnostics/state*`,
  `command_interface/run`. `diagnostics/ping/get` returns only the form model, it does not execute.
- OPNsense API: needs `--user "$KEY:$SECRET"`; without it every endpoint answers **302** (not 401),
  which looks like a path problem. `routes/gateway/status` works; `core/service/*`,
  `diagnostics/ppp/*`, `shaper/*`, `interfaces/*/get*` are 404. Log endpoints answer 200 with an
  empty body for GET, so the firewall's own logs are not reachable this way.
- `?serverId=` on speedtest-exporter is ignored; the exporter chooses the server itself.
- Prometheus `resets()` returned no series for a target that clearly has data - prefer testing
  counter decreases with `delta() < 0`.
- `last_over_time(m[2h])` finds hourly samples that `avg_over_time(m[50m])` misses entirely, because
  step alignment can straddle them.
- Prettier wraps a long `- alert: SomeVeryLongAlertName` onto its own line. A parser using
  `^\s*-\s*alert:\s*(\S+)` silently misses those rules (the repo has 66 alert names in 19 rule files;
  my first pass under-counted, including `AutobrrDatabaseIsMalformed`). Match the name on the
  following line too.
- `/api/v1/rules?rule=NAME` is not a usable filter here (the response had no `data` key); pull the
  whole rules payload and filter in-process.
- `absent(v{a="b"})` copies the selector's literal matchers onto its output series, so
  `{{ $labels.a }}` does render inside an absent-based alert.
- To tell "quiet" from "blind", compare `ALERTS` history with the rule's `activeAt`: a pending alert
  whose `activeAt` keeps advancing is being reset by a flapping condition, not waiting patiently.
- Never read `$?` after a pipe - `task ... | tail -12` reports tail's status and discards the evidence.
  Capture the full log, then grep it for the specific thing you claim was checked.
- No `wireguard_*` metric family exists: the exporter is the OPNsense one, so the names are
  `opnsense_wireguard_peer_last_handshake_seconds` (note: `last`, not `latest`) and
  `opnsense_gateways_*` (plural).
- Do not dump `/api/v1/label/device/values` - node_exporter enumerates every lxc, zpool and nbd
  device and the response buries the rest of the output (wg1/wg2 are in there, at ~1k entries).

**Dead remediation path found while checking routing (`observability/kube-prometheus-stack/app/resources/alertmanager.yaml:34-38`).**
A route sends `alertname = "VolSyncVolumeOutOfSync"` to the `remediation-webhook` receiver, but that
alert's rule file is not loaded (volsync retired) - so an automated remediation exists that can never
be invoked. Fold removing this route into the volsync cleanup decision.

Routing verified for #2607: `severity="critical"` → discord **and** pushover (all four new coverage
alerts), `severity="warning"` → discord via the root route (so the corrected `OpnsenseServiceStopped`
will actually page about CrowdSec once this merges). The only mute window, `kopiur_ssd_backup_window`,
is scoped to the Kopiur route and cannot silence anything added here.

CI note: `Image Pull - Extract Images` fails on this PR with
`HelmRelease/...: chart source OCIRepository/<ns>/app-template not ready: dependency not found` —
identical failure on merged #2604, so it is a pre-existing CI/flate problem, not caused by a YAML-only
change (this PR touches no HelmRelease and no image reference).

---

## 2026-11-27 — Volsync removal (steps 033–036), branch `chore/remove-volsync`

**Ask:** "continue, remove volsync then." — volsync is retired (kopiur + Kopia replaced it), so its Git
config is dead weight rather than something to repair.

**Scope decisions the user made before any edit** (both were recommended options):
1. Remove the whole remediation vertical slice, not just the volsync dirs — `jobs/remediation`,
   `observability/webhook` and the alertmanager route/receiver exist only to restic-unlock stalled
   volsync backups; keeping them means a dead webhook Deployment plus a route to nothing.
2. Strip everything per-app — commented includes, `VOLSYNC_*` substitutions and the
   `volsync.backube/privileged-movers` annotations — so no reference survives in `kubernetes/`.

**Why the deletion is safe (033, `results/033-volsync-removal-inventory.txt`):**
- 0 active `components/volsync` includes; all 48 are commented out.
- No `dependsOn`, `path:`, NetworkPolicy or DNS reference to `volsync-system` from any live app. The only
  `dependsOn` entries naming volsync lived inside `kubernetes/apps/volsync-system/` itself.
- 0 volsync CRs cluster-wide; the `volsync-system` namespace holds only Flux notification leftovers
  (`alert`/`provider` ×2, `ocirepository/app-template`, 2 secrets, `serviceaccount/default`, 0 PVCs).
- `snapshot-controller` is independently live from `kubernetes/apps/kube-system/snapshot-controller`
  (HelmRelease `kube-system/snapshot-controller`, chart 5.4.0) — the copy under `volsync-system` was a
  duplicate, and kopiur's local snapshots use the kube-system one.

**Mechanical strip (034, `scripts/034-strip-volsync-per-app-config.py`).** 48 includes + 41 vars + 21
annotations across 70 files. Two things worth keeping:
- the guard that deletes a parent key whose body vanished is *tested*, not assumed — a synthetic case
  (`components:` holding only the volsync comment) correctly cascaded `components:` → `substitute:` →
  `postBuild:`, and a case where `APP` survives correctly keeps `substitute:`;
- the first version under-counted (47 of 48) because garage's doubly-commented
  `#   # - ../../../../components/volsync` does not match `^\s*#*\s*- `. Comment markers can repeat and
  can be space-separated. Ground truth was re-derived with `git grep` and matched exactly before `--apply`.

**Verified on the committed branch:** kubeconform exit 0 / 1110 resources valid / 0 invalid (full log,
`results/036-kubeconform-final-branch.log`); `kustomize build` passes for all 21 touched namespaces (the
22nd is the deleted `volsync-system`); all 79 touched YAML/JSON files parse; `task --list` loads with no
volsync namespace; no caller of `just k8s snapshot` remains; both edited Python scripts compile.
Prettier: I introduced drift in the two tuppr files (comment indent) and fixed it; `alertmanager.yaml`
was already unformatted on main (one comment-alignment line) and the `--write` hook normalised it.

**Left deliberately, reported rather than silently changed:**
- `kubernetes/apps/storage/kopia/app/helmrelease.yaml` — the Kopia repository user `volsync`
  (`hostname: volsync.storage.svc.cluster.local`). Old volsync archives are owned by that user; deleting
  the policy entry could make existing archives unreachable in the UI. Not a config error, a data
  access decision.
- `infrastructure/ansible/playbooks/fileserver.yaml` `/tank/Backup/Volsync` and `/tank/Backup/Volsync/*`
  on the fileserver: backup *data*, not config.
- `scripts/populate_waf_prr.py` `{m_volsync}` / `has_volsync`: the flag feeds a PRR template string, and
  dropping the dict key while the `{m_volsync}` placeholder stays would raise KeyError at format time.
  After this PR the flag is permanently `[ ]`, and the generated sentence still says "via VolSync".
  Needs a kopiur re-point, which is a doc-tooling change of its own.
- `scripts/migrate_to_oci.py` — one-off migration script; the volsync OCI mapping and its past-failure
  docstring are history.

**Cluster effects to expect on merge:** `cluster-apps` has `prune: true` (24 h interval), so Flux deletes
the `volsync-system` Namespace and its 7 leftover objects, `deployment/remediation-webhook`
(observability) and `cronjob/remediation` (jobs). The three volsync CRDs
(`replicationsources`, `replicationdestinations`, `kopiamaintenances.volsync.backube`) linger — deleting
a CRD is a separate, approved mutation and would also need the tuppr health-check question revisited.

**PR #2608 opened: `chore/remove-volsync`** (https://github.com/chaijunkin/home-ops/pull/2608), 6 commits,
139 files, +42/−2016. Final gate on the committed branch: `task kubernetes:kubeconform` exit 0,
**1110 resources valid, 0 invalid** (`results/036-kubeconform-final-branch.log`), after
`kustomize build` passed for all 21 surviving namespaces and the repo-wide null-key scan showed zero
overlap with the PR's files. The PR body states the cluster effects (namespace + webhook Deployment +
remediation CronJob pruned; CRDs deliberately left) and lists the four things left in place on purpose.

### CI on #2608: the image job fails, and the real numbers

`Image Pull - Extract Images` went red (`mergeStateStatus=UNSTABLE`; `main` is unprotected so it is not a
required check). Reading the log properly instead of stopping at "pre-existing":

```
orig snapshot:    reconcile completed with 38 failure(s)   <- base = main
current snapshot: reconcile completed with 36 failure(s)   <- chore/remove-volsync
flate error: both snapshots had reconcile failures
```

All 74 lines are one class: `chart source OCIRepository/<ns>/app-template not ready: dependency not found`.
The 38→36 delta is exactly `jobs/remediation` and `observability/remediation-webhook`, which exist only on
the base side because this PR deletes them — **the branch strictly reduces the failure set**, and no
`volsync` string appears anywhere in the output.

**Retraction of my earlier wording.** I had written that the failure is "identical" to the one on #2604.
It is the same *class*, not the same *set*: the number of not-ready HelmReleases depends on how wide a
diff flate has to render (3 entries on the 4-file alerting PR, 38 here). Saying "identical" without the
counts would have hidden the fact that this PR's diff makes flate render ~70 apps.

Also: "0 volsync mentions in the failure log" is true but was not sufficient evidence on its own, because
the log *does* name the two removed HelmReleases (as base-side entries). The decisive evidence is the
base-vs-head failure count plus the absence of any missing-directory/unresolved-reference error.

Local reproduction is a dead end worth recording: `flate diff images -p ./kubernetes/apps -o json` with the
same pinned `flate 0.6.5` exits 0 with `[]` on both `origin/main` and this branch, because off-CI it does
not do the cluster walk that produces the `app-template` resolution. A green local run here proves nothing;
only the CI snapshot comparison does. Posted as a PR comment for reviewers.

## Day 5 — 2026-11-27, post-#2608 prune, and a rule that was permanently pending (steps 037-041)

#2608 merged 2026-11-26T19:30:28Z as `1376817d2`. Step 037 re-snapshotted the cluster: Flux had already
pruned `deployment/remediation-webhook`, `cronjob/remediation` and every volsync-named Kustomization, and
`kube-system/snapshot-controller` is still 1/1 — the thing this PR could have destroyed survived. Two
things did not behave as expected.

**1. `volsync-system` Namespace survived on purpose.** It carries
`kustomize.toolkit.fluxcd.io/prune: disabled`, so Flux removed everything inside it (only
`kube-root-ca.crt` and the `default` ServiceAccount remain) and left the Namespace object itself. Deleting
it, and the three surviving `volsync.backube` CRDs, is a separate approved step, not a prune.

**2. `SpeedtestExporterAbsent` — I reported this as "firing (critical)" and that was wrong.** Step 040
shows it in `pending` with **zero firing samples in 24h**:

```
count_over_time(ALERTS{alertname="SpeedtestExporterAbsent",alertstate="firing"}[24h])  -> (empty)
count_over_time(ALERTS{alertname="SpeedtestExporterAbsent",alertstate="pending"}[24h]) -> 2640
count_over_time(ALERTS{alertname='Watchdog'}[24h])                                     -> 2880
```

2640/2880 = 91.7% = **55 minutes of every 60**. The exporter itself is provably fine: 24 samples in 24h
(one per hour, landing at :31:40), `min_over_time(up[24h]) == 1`, `avg_over_time(...[4h])` = 909 Mbps down
/ 519 Mbps up / 7.3 ms.

The arithmetic behind it, which is the actual finding: the ServiceMonitor scrapes every **60m**, and
Prometheus drops a series from *instant* queries ~5m after its last sample. The rule is
`absent(up{job=~".*speedtest-exporter.*"} == 1)`, and `up == 1` is therefore only selectable for ~5m of
each hour — absent() is true the other 55m, so the alert sits pending and is reset by the next hourly
scrape before `for: 75m` can ever elapse. `for: 75m` is the only reason it is not a false page every hour;
if someone "tidies" that down to 10m it fires hourly.

Steps 038 and 039 could not see this because *every* query I used there inherits the same 5-minute
lookback: `/api/v1/series` defaults to a 5m window, an instant query inherits it, and my 3600s-step range
query on hourly samples steps straight past it. Only `/api/v1/label/__name__/values` (whole retention) and
`count_over_time` are immune. Writing "no series" three times in a row and calling the metric gone was the
mistake; the metric was there the whole time.

**Audit of the other `absent()` rules (step 041):** `speedtest-exporter` at 1h is the only slow target in
the cluster — opnsense-exporter 1m, cert-manager 1m, everything else 30s — so no other bare-`absent()`
rule inherits this. The two selectors I shipped in #2604 were explicitly checked for the opposite failure
(a selector matching nothing is a permanently-true critical): both match live series
(`probe_success{service="blackbox-exporter-vpn"}` exists on `job=probe/observability/vpn-{icmp,http}`, and
`opnsense_wireguard_peer_last_handshake_seconds{device="wg2"}` too), and neither has a single ALERTS sample
in 24h, which is the correct behaviour for a coverage rule while the source is alive.

**The replacement, evaluated live in three shapes before writing it:**

```
absent_over_time(up{job=~".*speedtest-exporter.*"}[130m])
  or
max_over_time(up{job=~".*speedtest-exporter.*"}[130m]) == 0
```

empty while healthy; `1` when the target stops producing samples entirely; empty on the second arm against
the live healthy target. Both arms are required — `absent_over_time` cannot see a target that answers with
`up=0`, `max_over_time` cannot see a target that stopped producing samples. Range windows are unaffected
by the staleness lookback, and 130m spans more than one hourly scrape.

**Also named:** the 4 `KubeJobFailed` are `ai-inference-smoke-test-29927880/-29928240/-29928600` (ns `ai`,
hourly) and `chaijunkin-discovery-6de9ae35b4t77` (ns `renovate`). `KubeHpaMaxedOut` is 22 wide.

**Tooling notes.** `/api/v1/rules` needs ~120s to answer through the port-forward; a 25s timeout made step
038's rule-health section fail *silently*, which is how a "everything checked" claim nearly went out with a
hole in it. Group objects in this Prometheus version have keys `['evaluationTime','file','interval',
'lastEvaluation','limit','name','rules']` — **no `namespace`**, so `g["namespace"]` raises KeyError
mid-report; use `g["file"]`.

### The fix, shipped as PR #2610 (step 042)

Branch `fix/speedtest-absent-staleness`, one file. Step 042 extracts the `expr:` block out of the
committed YAML by indentation and evaluates it verbatim, so what is tested cannot drift from what is
committed: healthy cluster -> EMPTY, same text with a job that has no samples -> `['1']`, the other four
rules in the file still parse and do not fire. `kubeconform -strict` against `crd.cloudjur.com` reports
the rule valid; `prettier --check` clean.

**The CI failure names this PR's app and is still not ours.** `Image Pull - Extract Images` printed

```
orig snapshot:    reconcile completed with 1 failure(s): HelmRelease/observability/speedtest-exporter:
                  chart source OCIRepository/observability/app-template not ready: dependency not found
current snapshot: reconcile completed with 1 failure(s): <byte-identical>
```

Identical text, equal counts on both sides — the app is named only because the diff touches it. New
mechanism learned: the second red job is downstream, not independent. When flate exits on "both snapshots
had reconcile failures" it emits no output block, so the `$GITHUB_OUTPUT` heredoc dies with `Invalid
value. Matching delimiter not found 'EOF'` and `Image Pull - Success` fails on *that*. Two red jobs, one
cause. Recorded on the PR as `#issuecomment-7202790969`.

**Standing risk:** as of this writing `chat.md` carries **676 uncommitted lines** and the scripts/results
for steps 010-042 are untracked. The audit trail exists only in this working tree.
