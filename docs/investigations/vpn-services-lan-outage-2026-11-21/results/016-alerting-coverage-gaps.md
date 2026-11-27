# Result 016 — What alerting is still missing (audited, not guessed)

`scripts/023-alerting-coverage-audit.py`, `scripts/024-dead-rule-forensics.py`, 2026-11-26 ~09:20 MYT.

Method: extract every `expr:` from all rule manifests under `kubernetes/apps` (77 rules), pull the
full live metric-name inventory (4 856 names) from Prometheus, and diff. A rule that references a
metric which does not exist **can never fire**, and in the UI it is indistinguishable from "working
and healthy". Then, for each hit, decide whether it is my regex matching a label name, a renamed
metric, or an exporter that is not running.

**Correction first: PR #2594 is MERGED** (`05e4eec7d`, 2026-11-26T01:40Z). My earlier "still open,
please merge it" was read before the merge landed. Consequence, verified live:
`opnsense_services_status{name="crowdsec"} == 0` is true right now and `ALERTS{alertname="OpnsenseServiceStopped"}`
is **pending for crowdsec** — so the five-days-stopped IPS *is* covered by the scoped rule. It was the
unscoped `opnsense_services_stopped_total` (a single label-less counter, value `2`) that could not name
which service had died.

---

## 1. Six rule groups are protection that does not exist

> **Correction, added after `scripts/025`–`030`.** This table mixed two different problems, and only
> one of them is an alerting gap. Checking the loaded rule set (`/api/v1/rules`, 421 rules) rather
> than just the manifests shows that the **smartctl and volsync files are not deployed at all** —
> zero loaded rules each — so they are obsolete config plus one real decision (no disk-health
> alerting), not silent gaps. The claim in the volsync row that "backup replication drift has no
> alert" is **retracted**: kopiur (which replaced volsync) ships 13 healthy rules backed by 37
> `kopiur_*` metrics — `KopiurBackupStale` (>172800 s), `KopiurLastBackupFailed`,
> `KopiurSnapshotFailed`, `KopiurRepositoryBreakerOpen` — over 79 snapshot policies, with the newest
> backup 14.4 h old at the time of checking. The four rows below that *are* loaded were fixed in
> **PR #2607**; see `results/019-deployed-rule-matrix.txt` for the deployed-vs-absent matrix.

| rule file | alert(s) | what is wrong | impact |
|---|---|---|---|
| `observability/exporters/smartctl-exporter/app/prometheusrule.yaml` | 7 rules: `SmartDeviceHighTemperature`, `SmartDeviceTestFailed`, `SmartDeviceCriticalWarning`, `SmartDeviceMediaErrors`, `SmartDeviceAvailableSpareUnderThreadhold`, `SmartDeviceInterfaceSlow` | **not deployed**: zero `smart*` metrics in Prometheus and the exporter is commented out in `exporters/kustomization.yaml:7` (`# - ./smartctl-exporter/ks.yaml`) | **no disk-health alerting at all** — a degrading disk on the NAS is silent until data loss. This is a switched-off feature, so the decision is deploy-or-delete, not repair |
| `volsync-system/volsync/app/prometheusrule.yaml` | `VolSyncVolumeOutOfSync` | **not deployed**, and volsync itself is retired (all three `ks.yaml` entries are commented out in `apps/volsync-system/kustomization.yaml`; 0 PVCs carry kopia/volsync annotations). CRDs remain in the cluster as leftovers | obsolete config to delete. Backups are covered by kopiur instead — see the correction above; the old "drift has no alert" claim here was wrong |
| `network/cloudflare-tunnel/app/prometheusrule.yaml` | `CloudflareTunnelOffline` | `cloudflared_tunnel_user_connections` was renamed upstream; live name is `cloudflared_tunnel_ha_connections` | **loaded and unfireable** — tunnel offline detection was silently off (fixed in #2607) |
| `downloads/autobrr/app/prometheusrule.yaml` | `AutobrrNetworkUnmonitored` | `autobrr_irc_channel_monitored_total` / `_enabled_total` don't exist; live names are `autobrr_irc_enabled_total`, `autobrr_irc_healthy_total`, `autobrr_irc_total` | **loaded and unfireable** — an IRC network silently unmonitored goes unnoticed (fixed in #2607) |
| `database/dragonfly-operator/cluster/prometheusrule.yaml` | `DragonflyHighMemoryUsage` | `dragonfly_used_memory_bytes` / `dragonfly_memory_limit_bytes` don't exist; live names are `dragonfly_memory_used_bytes` / `dragonfly_memory_max_bytes` | **loaded and unfireable** — cache/redis memory pressure unalerted (fixed in #2607) |
| `ai/litellm/app/prometheusrule.yaml` | `LiteLLMFallbackChainExhausted`, `LiteLLMModelFailover` | `litellm_deployment_failed_fallbacks_total` / `litellm_deployment_successful_fallbacks_total` are not exposed by this litellm version at all (no `*fallback*` metric among its 72) | **loaded and unfireable** — "all fallbacks exhausted" never fired; re-expressed from the success/failure counters in #2607. The latency/failure-rate rules in the same file **do** work (`AIObservabilityHighLatencyP95` is firing now) |

Three of these were pure rename bugs and one pair needed re-expressing — all shipped in #2607.
`smartctl` needs a decision (deploy the exporter or delete its rules); volsync needs its dead config
removed. `snapshot-controller` must **not** be removed with it: it runs in `kube-system` (1/1, 116 d)
and kopiur's local-tier snapshots depend on it.

**My audit's own false positives, listed so nobody chases them:** `requested_model`,
`exception_class`, `exception_status`, `fallback_model`, `exported_namespace` are **label** names
inside `by (...)` / matcher blocks, not metrics. `litellm_llm_api_latency_metric` looks absent to a
bare name query because it is a histogram (`_bucket`/`_count`/`_sum` exist) — the rules that use it
are fine. `litellm_model_name` still needs a manual look: if it is used in `by ()` and the label
does not exist, the aggregation silently collapses instead of failing.

## 2. Coverage-presence: the failure mode this whole audit just demonstrated

**A missing series never equals `0`.** Every threshold rule is blind when its exporter disappears.
The one coverage-presence alert that existed before #2607 was `OpnsenseFirewallUnreachable`
(`up{job="node-exporter", instance=~"gateway.*"}`), i.e. the firewall alone.

The real instances of this class were not smartctl/volsync (those are switched off deliberately);
they were `probe_success{service="blackbox-exporter-vpn"}`, `up{job="opnsense-exporter"}` and the
wg2 peer series — all live, all watched by nothing. If any had gone away during the outage, the VPN
alerts would have stopped firing for the worst possible reason. #2607 adds exactly that layer:
`OpnsenseApiExporterAbsent`, `OpnsenseExporterEndpointErrors`, `VpnEgressProbesAbsent`,
`VpnEgressTunnelAbsent`. Two live metrics made a cheap version possible and were previously
unalerted:

- `opnsense_exporter_endpoint_errors_total` — the exporter partially erroring while `up == 1`
  (22 series, max over 30 d = 0, so `>0` is signal and not noise)
- `up{job="opnsense-exporter"}` alongside the existing node-exporter rule

**A second failure mode the audit found, which no amount of metric-name checking catches:** a rule
whose condition *flaps* can never satisfy `for:`. `OpnsenseServiceStopped` (#2594, merged) compared
`opnsense_services_status{name!~"iperf"} == 0`; the firewall reports crowdsec as running for one
scrape every ~15 minutes while it is actually stopped — 31 of 361 one-minute samples over 6 h, 62
transitions. Each false evaluation resets the pending timer, so the alert stayed `pending` for 5 h
40 m with CrowdSec down and never notified. `min_over_time(...[10m]) == 0` fixes it (verified
continuous, 46/46 samples). Rule of thumb for the runbook: *if the input can flapper, the condition
needs a look-back window, and `for:` alone will not save you.*

## 3. Gaps this incident proved real and nothing covers yet

1. **`VpnEgressLeakingToWAN` (egress identity)** — still the highest-risk uncovered case. If VLAN 31
   ever falls back to the default route, sabnzbd/slskd run on the residential IP **with no alert**;
   today's failure mode is loud, this one is silent. Needs a prober that publishes the observed
   public egress IP of the VPN path as a metric, then alert when it is not a Proton range.
2. **WG peer unreachable** — `time() - opnsense_wireguard_peer_last_handshake_seconds > 300` for the
   exit peer only. Distinct from `VpnTunnelUpButNoReturn`: this one catches the crypto layer dying
   (dead gate, rotated key, endpoint gone) where today a peer simply stops being observable. Live
   data confirms the scoping requirement: `wg2/ProtonVPN_Singapore` age ≈ 142 s, while both
   `wg1` peers report `1 795 657 639 s` (i.e. handshake `0`, never) and would page forever.
3. **VLAN 32 egress is silently denied** (found earlier: `10.10.32.x → 16.163.195.33:9999` and NTP
   denied by filter rule 13). No probe exists for that path, so a whole VLAN's outbound is broken
   with no signal. Either fix the rules or add a probe; don't leave it ambiguous.
4. **Firewall deny storms**: `opnsense_firewall_in_ipv4_block_packets`,
   `opnsense_firewall_out_ipv4_block_packets` (and ipv6) exist and are unalerted. A fat-fingered
   filter change or a scan is invisible today.
5. **Firewall housekeeping**: `opnsense_firmware_needs_reboot`,
   `opnsense_firmware_upgrade_needs_reboot`, `opnsense_firmware_new_packages` exist, unalerted. On a
   box that also runs the IPS, "unrebooted since the upgrade" is a security signal.

## 4. The uncomfortable finding: detection worked; action did not

Notification delivery is healthy — `alertmanager_notifications_total` **2 327 sent in 7 d, 1
failed**, and `severity="critical"` routes to both Discord **and** Pushover. So `VpnProbeFailed`
(critical, `for: 15m`) paged continuously for **five days** and the incident still ran its course.
Adding alerts is therefore not the fix for that class of failure. What is missing:

- **No acknowledgement or escalation.** Discord + Pushover are fire-and-forget; nothing re-pages an
  unhandled critical, and nothing escalates an alert that has been firing for hours. A cheap version:
  an escalation route on `ALERTS{alertname=~"...",alertstate="firing"}` sustained 6 h.
- **Standing noise burying signal.** Currently firing: `KubeHpaMaxedOut` ×22, `KubeJobFailed` ×4,
  `BlackboxProbeFailed` ×2, `VpnProbeFailed` ×2, `LinuxNodeHighMemoryUsage`,
  `NodeMemoryHighUtilization` (two rules, same condition), `AIObservabilityHighLatencyP95`,
  `Watchdog`. ~32 firing alerts means a new critical is one more line in a channel that is always red.
- **Two of those are real breakage, not noise**: `KubeJobFailed` is `ai-inference-smoke-test` ×3
  (ns `ai`) and a `chaijunkin-discovery` job (ns `renovate`) — failing unattended and unread.
- **No runbook in the alert** (deliberate, because the investigation docs are untracked). If these
  alerts are meant to be actionable by someone other than me, the runbook has to land in the repo.

## Priority I would use

1. Volsync drift + SMART disk health — both are silent data-loss paths with zero coverage.
2. Coverage-presence rules for the monitors themselves (§2), so "gone" can never look like "fine".
3. The three rename fixes (cloudflared, autobrr, dragonfly) — five minutes each, restores real protection.
4. `VpnEgressLeakingToWAN` — the only remaining path where a failure makes things *worse silently*.
5. Clear the 32-alert baseline and add an escalation route, or the next critical gets ignored too.
