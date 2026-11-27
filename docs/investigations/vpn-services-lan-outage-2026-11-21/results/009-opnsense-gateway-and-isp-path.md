# Result 009 — Is it the OPNsense gateway? No: it is the ISP's first hop

`scripts/010-opnsense-api-health-sweep.sh` (read-only, GET-only) + traceroute, 2026-11-24
~22:45–23:15 MYT (14:45–15:15 UTC).

## The answer, in one line

Traceroute hop 2 is the ISP's own gateway and it is **already 120–142 ms**:

```
 1  (firewall 192.168.1.1)                    6-9 ms   (from the Mac: 6.2/9.0/12.7)
 2  isdn-tsk-239-254.tm.net.my (210.186.239.254)  131.2  120.8 ms   <-- Time dotCom
 4  10.55.76.5                                138.3 ms
 8  unknown.telstraglobal.net (210.57.38.183) 173.2 / 112.2 ms   (transit)
 9  172.69.117.105 / .125                     264.3 / 156.5 ms
10  one.one.one.one (1.1.1.1)                 238.7 / 222.7 ms
```
Same shape for `8.8.8.8`: hop 2 at 142 ms, hop 3–4 at 125–135 ms, destination at 140 ms.

Everything after hop 2 just inherits it. Nothing inside the house can explain 120 ms on the
ISP's own gateway address.

## What the firewall itself says (API)

`GET /api/routes/gateway/status`:

| gateway | monitor | loss | delay | status_translated |
|---|---|---|---|---|
| `WAN_PPPOE` (210.186.239.254) | **`~` (none)** | **`~`** | **`~`** | "Online" |
| `WAN_ProtonVPNSingapore` (10.2.0.1) | 10.2.0.1 | 6.0 % | **146.2 ms** | "Online" |

Two things:

1. **`WAN_PPPOE` gateway monitoring is disabled**, so dpinger has *no* delay/loss data and
   reports "Online" purely because nothing is checking. The firewall has been blind to this
   whole degradation — and it was blind to the Nov 21 outage for the same reason.
2. The only monitored gateway pings **Proton's tunnel end**, and it went from 13 ms to
   **146 ms with 6% loss today** — the same upstream congestion, seen from a second direction.

## What the firewall is NOT doing

* **No traffic shaping at all.** `grep` of the live config: `shaper` 0, `limit` 0, `pipe` 0,
  `queue` 0, `altq` 0, `cake` 0, `fq_codel` 0, `hwoffload` 0. Nothing is throttling you, and
  equally there is no AQM protecting your latency under load.
* **No policy routes**: `GET /api/routes/routes/get` → `{"route":{"route":[]}}`.
* **Resources have headroom**: pf states 9,445 / 799,000 (1.2%), mbuf 14,224 / 494,532 (2.9%),
  `node_load1` avg 0.45 / max 2.7 over the retained window.
* **The PPPoE session did not drop** and upload still measures ~500–530 Mbps in every sample.
* **Traffic did not move onto the WireGuard tunnel** — `opnsense_wireguard_peer_received_bytes_total`
  is flat at 0.5–0.7 kB/s (handshakes only) across 12 h, TX 0.00 Mbps.
* **The Mac is not split-tunnelling** — `route -n get 1.1.1.1` / `8.8.8.8` both go via
  `192.168.1.1 dev en1`; no `0/1` or `128/1` routes, no proxy.

## Timeline of the degradation (from the exporter's own hourly log)

| local (MYT) | UTC | server | ping | download | upload |
|---|---|---|---|---|---|
| 20:28 | 12:28 | 45623 | **6.8 ms** | **912 Mbps** | 521 |
| 21:28 | 13:28 | 57148 | 132 ms | 108 Mbps | 470 |
| 22:04 | 14:04 | **45623** | **121 ms** | **162 Mbps** | 500 |
| 22:28 | 14:28 | 56172 | 128 ms | 206 Mbps | 526 |
| 22:38 | 14:38 | 70564 | 131 ms | 1.9 Mbps | 516 |

The 22:04 line is the one that rules out "the exporter picked a bad server": it used the *same*
server 45623 that had measured 6.8 ms / 912 Mbps an hour earlier, and measured 121 ms / 162 Mbps.
Samples at 21:28 and 22:28 are scheduled scrapes, not my test traffic.

`?serverId=` is **ignored** by this exporter build — requested 45623, got 44364; requested 57148,
got 70564. Server pinning has to be done another way (see recommendations).

## So: three separate problems, correctly separated

1. **ISP (Time dotCom) — new, active, and the reason things feel slow now.** Hop-2 at 120–142 ms,
   download collapsed from ~912 Mbps to 1.9–320 Mbps, upload unaffected → downstream congestion on
   their network. Started between 12:28 and 13:28 UTC (20:28–21:28 MYT).
2. **OPNsense configuration — real, but it causes blindness, not slowness.** WAN gateway
   monitoring disabled; the only monitor pings a VPN endpoint. Fix: enable monitoring on
   `WAN_PPPOE` with a public monitor IP (TM's BRAS may not answer), then an alert on
   `opnsense_gateways_rtt_milliseconds{name="WAN_PPPOE"} > 60` becomes meaningful — today
   `absent()` on that series is itself the evidence of the gap.
3. **The Nov 21 WireGuard egress failure — unchanged, still provider-side**, and now plausibly the
   same operator's network: TM hop 2 was already 120 ms on the way to Proton as well.

The Mac's earlier 115 Mbps / 217 ms idle latency is a *consequence* of (1) plus a slower Wi-Fi link;
its ping to the gateway is 6–9 ms, i.e. the LAN is fine.

## Recommendations

* **Ticket to Time dotCom** with: hop-2 `isdn-tsk-239-254.tm.net.my` at 120–142 ms sustained since
  20:28 MYT, download 912→~200 Mbps, upload steady ~520 Mbps, PPPoE session stable, and the note
  that a 3-day-old separate fault (no return traffic into a WireGuard tunnel via their network)
  may be related.
* **Enable gateway monitoring on `WAN_PPPOE`** (System ▸ Gateways ▸ WAN_PPPOE ▸ uncheck
  "Disable gateway monitoring", set a Monitor IP that answers). Without it dpinger cannot see an
  outage and no firewall-side alert can ever work.
* Optionally enable **CAKE on WAN** for latency under load — no shaper exists today — but it will
  not fix ISP congestion.
* **Pin the speedtest server** by another mechanism (`?serverId=` is ignored), otherwise the
  history stays incomparable.

## Incident during this step: working tree wiped, recovered

At 22:45 MYT a `git reset --hard` + clean removed two commits from
`fix/scope-opnsense-service-alert`, including the committed investigation log. Both were intact as
dangling commits and were recovered:

* `git tag recover/investigation-log-20261124 a18af682b` (19 files)
* `git tag recover/docs-curation-20261124 1d03b575f` (12 files: `APP_KNOWLEDGE`/README curation —
  **not mine**, still needs re-landing: `git cherry-pick 1d03b575f`)
* Archives in the approved temp dir under `recovered/`.
* `docs/investigations/` restored into the working tree **unstaged** via
  `git archive a18af682b docs/investigations | tar -x -C .`, keeping it out of the PR.
