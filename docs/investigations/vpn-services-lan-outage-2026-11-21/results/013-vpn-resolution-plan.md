# Result 013 — How to resolve the VPN probe alert: the tunnel is fine, Proton's forwarding is dead

`scripts/016` … `scripts/021`, 2026-11-26 08:08–08:35 MYT.

## Why the alert has not cleared, in one line

The ISP path recovered (hop 2 back to 13 ms, 0 % loss) but **VLAN 31 still gets nothing back from
Proton**, so `VpnProbeFailed` is still correct. The firewall is doing everything right:

Four known flows were generated from `10.10.31.15` (metube) and each one is logged **twice**,
exactly as configured:

| logged on | rule | source | destination |
|---|---|---|---|
| `vlan0.31.1` | 145 (allow VLAN 31 egress) | `10.10.31.15:42576` | `1.1.1.1:443` |
| `wg2` | **110** (policy route into the tunnel) | **`10.2.0.2:28990`** | `1.1.1.1:443` |
| `vlan0.31.1` | 145 | `10.10.31.15:38828` | `162.159.200.1:123` |
| `wg2` | 110 | **`10.2.0.2:34566`** | `162.159.200.1:123` |
| `vlan0.31.1` | 145 | `10.10.31.15:52408` | `172.67.74.152:443` (api.ipify.org) |
| `wg2` | 110 | **`10.2.0.2:19677`** | `172.67.74.152:443` |

* policy routing **applies** (rule 110, never `pppoe0`)
* outbound NAT **rewrites** to the tunnel address `10.2.0.2`
* **zero return rows.** Not one reply, on any interface.

And the tunnel itself is provably alive: dpinger reaches Proton's tunnel end `10.2.0.1` at
**13 ms / 0 % loss**, and `wg2` keeps exchanging 0.6 kB/s of handshake traffic. So crypto,
reachability and keying are all working — **only traffic beyond the tunnel disappears.** That is
Proton's forwarding plane, not ours.

## Hypotheses tested and eliminated today

| hypothesis | test | result |
|---|---|---|
| MTU / PMTUD blackhole (`wg2` MTU unset = 1500, **0 MSS clamps**) | MSS sweep from a VLAN-31 pod: 1460, 1452, 1440, 1436, 1420, 1400, 1380, 1360, 1340, 1280, 1220, **1000** (`scripts/019-mss-sweep.py`) | **all 12 fail**, every one `SSL: UNEXPECTED_EOF_WHILE_READING`. Not MTU. |
| TLS-specific problem | `http://example.com/`, `http://1.1.1.1/` | both time out → not TLS |
| DNS problem | pod resolved `api.ipify.org` → `172.67.74.152`, logged on `wg2` | DNS fine |
| firewall dropping it | live log, 155 new rows, our 4 flows all `pass` | firewall clean |
| traffic escaping via the WAN instead of Proton | searched all new `pppoe0` rows for `10.10.31.*` / `10.2.0.*` sources | **none** — it really is going into the tunnel |
| ISP still degraded | ping ladder | hop 2 **13 ms / 0 %**, `8.8.8.8` **16 ms / 0 %** → recovered |
| tiny-payload limitation | NTP 48 B both ways to `162.159.200.1` | times out (outbound logged on `wg2`) |

One anomaly worth recording: in the first pass (`scripts/020`) closed ports `1.1.1.1:12345`,
`:8701`, `8.8.8.8:9999` reported *connected in 13 ms*, which no real path does. On the repeat the
same port timed out, and the pf log confirms only the outbound direction. Treat those
"successes" as noise — **`tcp_connect` is not a usable health signal on this path.**

## Resolution — the outage

1. **Change the Proton exit server.** The peer has been pinned to the literal endpoint
   `149.50.211.164:51820` since January 2026. That endpoint still completes handshakes but forwards
   nothing, which is precisely a decommissioned/mis-provisioned Proton server.
   *GUI:* **VPN ▸ WireGuard ▸ Instances ▸ `ProtonVPN-ExitSingapore` ▸ Edit ▸ Display Advanced ▸
   Peers** → replace *Endpoint* and *Public key* with a **different** Singapore logical server,
   save, then **Services ▸ WireGuard ▸ Apply**.
   *Cleaner:* re-run the Proton OpenAPI enrolment that built this in the first place (see
   `~/Documents/DefaultVault/journals/2024_03_17.md`) so the endpoint is chosen from the live
   server map instead of being hard-coded.
2. **Two-minute triage that splits "our config" from "their network":** install the Proton VPN app
   on a phone, **on mobile data**, and connect to a Singapore server.
   * app works → account and key are fine → it is this pinned server/endpoint → step 1 fixes it
   * app fails on mobile data too → Proton↔Time path or account issue → open a Proton ticket
3. **If a different server still fails: rotate the WireGuard keypair.** Proton completes the crypto
   handshake for an unauthorised key and then drops forwarded traffic — the exact symptom here.
   Generate a fresh keypair, enrol it via the OpenAPI, put the new private/public keys on both sides.
4. **Ticket text for Proton** (their side is the one that must act):
   > WireGuard tunnel to `149.50.211.164:51820` is fully established — the tunnel endpoint
   > `10.2.0.1` answers ICMP at 13 ms / 0 % loss and handshakes flow continuously — but **no
   > forwarded traffic ever returns**. Outbound NAT to `10.2.0.2` is confirmed by pf logs on `wg2`,
   > e.g. `10.2.0.2:28990 → 1.1.1.1:443` and `10.2.0.2:34566 → 162.159.200.1:123`, with zero return
   > packets. Not an MTU issue: an MSS sweep from 1460 down to 1000 bytes fails identically.
   > Failing since 2026-11-21 08:31 UTC. Please check forwarding on that server, or move my
   > endpoint to a healthy Singapore server.

## Resolution — the alerting, which is currently misleading

`VpnProbeFailed` is `probe_success{service="blackbox-exporter-vpn"} == 0` for 15 m, over two
probes (`kubernetes/apps/observability/exporters/blackbox-exporter/vpn/`).

**Retraction (26 Nov, 20-day hourly comparison):** on 25 Nov I wrote that `vpn-icmp → 1.1.1.1`
"can never pass because Proton does not forward client ICMP". **That was wrong.** Hourly data for
20 days:

```
day     icmp            http            agreement
11-11   ..........      ..........      10/10
11-12…20  (24/h)        (24/h)          24/24 identical, all green
11-21   ................XXXXXX  ................XXXXXX   22/22   <- outage begins 16:00 MYT
11-22…25  XXXXXXXXXXXXXXXXXXXXXXXX (all X on both)
11-26   XXXXXXXXX       XXXXXXXXX       9/9
totals: both-down 111, icmp-down-only 2, http-down-only 0
```

ICMP was green every day from 11 to 20 Nov, so Proton **does** forward it. **Keep both probes** — they
agree with each other 100 % of the time and neither produces false alarms (2 stray ICMP samples in
20 days). What this table really gives us is the outage boundary: **first failed sample 2026-11-21
16:00 MYT (08:00 UTC), still failing on 26 Nov — five straight days**, and it is one continuous
event, not the flapping the earlier 48-hour window suggested.

The genuine probe-design problem is the opposite one: **`tcp_connect` on this path reports success
during a total outage** (closed ports `1.1.1.1:12345`, `:8701`, `8.8.8.8:9999` all "connected in
13 ms"). So do **not** add a `tcp_connect` probe as a tie-breaker — it would have hidden this
incident.

Changes to make (PR):

1. Keep `vpn-icmp` and `vpn-http` as they are.
2. **Do not add a second HTTP target** (this was my earlier recommendation — reversed). `VpnProbeFailed`
   is `probe_success{service="blackbox-exporter-vpn"} == 0`, so a new target under the same `service`
   couples VPN alerting to a third-party endpoint's health: one Cloudflare/Akamai hiccup would page as
   "VPN down". The two current probes agreed on every one of 20 days checked and produced no false
   alarms, so there is nothing for a third target to buy. Instead the new rule requires **all** probes
   to fail (`max(probe_success{…}) == 0`), which keeps a single sick endpoint from impersonating a
   provider fault without adding a new dependency.
3. **Add `VpnTunnelUpButNoReturn`** — the signature of this whole incident, which no alert caught.
   **Validated against 20 days of real data** (`and on()` is required: the two metrics have
   completely different label sets, so a bare `and` matches nothing and the alert silently never
   fires — I hit exactly that while testing):

   ```promql
   (time() - opnsense_wireguard_peer_last_handshake_seconds{device="wg2",
                                                            peer_name="ProtonVPN_Singapore"} < 300)
     and on()
   (probe_success{service="blackbox-exporter-vpn"} == 0)
   ```

   Live evaluation at chosen instants:

   | time (MYT) | result | meaning |
   |---|---|---|
   | 13 Nov 09:00 | quiet | healthy |
   | 20 Nov 09:00 | quiet | healthy |
   | 21 Nov 18:00 | quiet | transition: handshake was stale, so neither half held together |
   | 23 Nov 09:00 | **fires**, handshake_age = 131 s | crypto alive, egress dead |
   | 25 Nov 21:00 | **fires**, handshake_age = 93 s | same |
   | 26 Nov now | **fires**, handshake_age = 127 s | still |

   Why this form rather than a throughput threshold: the exporter's own peer counters separate the
   two states by ~100× (`rate(opnsense_wireguard_peer_received_bytes_total{device="wg2"})*8/1e3` is
   **40.6–58.0 kB/s on healthy days, 0.5–0.7 kB/s during the outage**), so a threshold is possible —
   but it would false-positive the moment the tunnel is legitimately idle. Pairing *handshake
   freshness* with *probe failure* needs no threshold and is exactly the diagnostic that was missing.
   The `device="wg2", peer_name="ProtonVPN_Singapore"` scoping is mandatory: the inbound-only
   `wg1` peers (`Home_JK`, `Home_Wireguard_Family_Shared`) have `last_handshake = 0` and would match
   any unguarded expression forever.
4. **Add `VpnEgressLeakingToWAN`**: alert when VLAN-31 workloads' observed public IP is *not* in a
   Proton range. Silently reverting to `210.186.239.63` is the dangerous failure mode — downloads
   would un-proxy without any alert. Needs a tiny prober that publishes the egress IP as a metric.
5. Fix the two genuinely dead speedtest rules (thresholds `200`/`30` need `200e6`/`30e6`, because
   `speedtest_*_bits_per_second` is already bit/s: `922324560` **is** 922 Mbps).
   **`SpeedtestExporterAbsent` is correct as written — I retracted my "can never fire" claim.** The
   exporter is scraped hourly (`interval: 60m`), so `up` is fresh only ~5 min of each hour; `for: 75m`
   is deliberately longer than the scrape interval and fires when 75 consecutive minutes pass with no
   good scrape. Switching it to `absent_over_time` would only make it twitchier.
6. Add `OpnsenseGatewayMonitoringDisabled` + `OpnsenseGatewayDegraded`. (PR #2594 **merged**
   2026-11-26T01:40Z as `05e4eec7d`; verified live that `OpnsenseServiceStopped` is now pending for
   `crowdsec`, which the old label-less `opnsense_services_stopped_total` counter could not name.)
7. ~~Add a `runbook_url` annotation pointing at this file.~~ **Deliberately skipped:** the
   investigation folder is untracked by design, so a `runbook_url` here would be a dead link for
   whoever the alert pages. Add it if this write-up ever lands in the repo; until then the alert
   annotations carry the diagnosis themselves.

## Hygiene while Proton is broken

`wg2` carries **MTU 1420** (set on the WireGuard instance, not the interface — I first read the
interface and wrongly reported 1500), over a PPPoE (1492) path, with **zero MSS clamping anywhere**.
1420 + 60 = 1480 ≤ 1492, so the arithmetic is fine and it is not today's cause — MSS 1000 fails too.
Once the exit works, large flows still depend on PMTUD working end to end, so **clamp MSS to 1360 on
the VLAN-31 → VPN forward rules** rather than relying on ICMP.
