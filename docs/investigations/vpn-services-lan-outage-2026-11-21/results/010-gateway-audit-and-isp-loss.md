# Result 010 — Gateway/WAN config audit (no HA, no LB, no shaper — plus three real faults)

`scripts/011-gateway-level-stability.sh`, `scripts/012-gateway-config-audit.sh`,
2026-11-25 21:10–21:25 MYT. Answers *"check my gateway level; I think it is the gateway, I do not
have two."*

## Your instinct is right about the design — and it explains the symptoms

The config has **no fault tolerance on the exit path**:

| checked | present? | what that means |
|---|---|---|
| Gateway groups (`<load_balancer>`) | **0 groups** | no WAN+VPN failover, no pool → **no multi-gateway** |
| Gateway items | 3, listed below | one usable IPv4 default |
| Policy rules (`staticroutes`/policy) | **0 policy rules** | nothing can bypass a dead gateway |
| CARP / virtual IPs | only `localhost` 127.0.0.1 | single firewall, no redundancy |
| Traffic shaper / altq / dnshaper | **none configured** | no queue management at all — see below |
| Interface groups (`<ifgroups>`) | empty | nothing bonded |

**Gateways:**

| name | gateway | interface | disabled | monitoring |
|---|---|---|---|---|
| `WAN_PPPOE` | *(PPP-provided)* | `wan` (pppoe0) | no | **DISABLED** |
| `WAN_ProtonVPNSingapore` | 10.2.0.1 | `opt12` (wg2) | no | enabled |
| `Wireguaurd` | *(empty)* | `opt9` (wg1) | **yes** | — |

So: **one real gateway, monitored off, plus one dead leftover entry, and no load-balancing group.**
When the ISP link degrades or the VPN dies, pf keeps using it and every existing connection hangs
until its own timeout. There is nothing to fail over to — that is a design fact, not a guess.

## Three gateway-level faults that are actionable, in priority order

1. **`WAN_PPPOE` gateway monitoring is OFF (`monitor_disable=1`) with empty `latencyhigh`,
   `losshigh`, and `monitor_killstates=0`.** Consequence, stated precisely: the *gateway layer* had
   no signal at all — dpinger ran nothing for the WAN, so the firewall never marked it down and never
   killed its dead states (which is why existing connections hung instead of failing fast). It is
   **not** true that nothing alerted: `SpeedtestHighPingLatency` and `SpeedtestHighJitterLatency`
   *did* fire through the 24–25 Nov episode, verified after the fact against stored samples (4 h
   averages of **154.6 ms** ping and **181.7 ms** jitter at 25 Nov 23:28 MYT, quiet today at ~7 ms).
   **Fix:** enable monitoring, monitor IP `1.1.1.1`, set latency thresholds **30 / 100 ms**, loss
   **1 / 10 %**, and tick **kill states on gateway failure**.
2. **The VPN gateway is monitored with `10.2.0.1` — Proton's own tunnel end.** It answers even when
   Proton forwards nothing, so the gateway showed "online" through the entire VPN outage. The stored
   dpinger series proves it directly: `opnsense_gateways_rtt_milliseconds{name="WAN_ProtonVPNSingapore"}`
   held **12.8–24.7 ms across 21–23 Nov, the whole non-forwarding outage**, and only inflated to
   **125–160 ms on 24–25 Nov** when the underlying ISP path itself degraded (because the tunnel end
   is reached over that path). Gateway monitoring therefore cannot see provider non-forwarding at
   all — which is why `VpnTunnelUpButNoReturn` keys on handshake freshness *plus* probe failure.
   **Fix:** set the monitor IP for `WAN_ProtonVPNSingapore` to a real Internet address that must
   traverse the tunnel (e.g. `1.1.1.1`), not the peer's tunnel address.
3. **Dead gateway `Wireguaurd`** (typo'd name, disabled, **empty gateway address**) still on `opt9`.
   **Fix:** delete it — it is exactly the kind of entry that misleads a future troubleshooter.

**Also worth noting (not today's cause):** there is **no traffic shaper/priority queue anywhere**.
On a shared upstream, any bulk upload (Time Machine to `192.168.1.149`, restic to Wasabi, VPN
encapsulation) starves interactive ACKs, which is what "everything crawls but speedtest is fine"
usually feels like. **Fix:** a CAKE/prio queue on WAN with a small upstream reserve (~5 %).

## What I ruled out at the gateway/interface level, with numbers

| possible cause | evidence | verdict |
|---|---|---|
| NIC errors / drops / collisions | `igc0-3`, `wg1`, `wg2`: collisions 0, drops 0, errors 0 | ruled out |
| PPPoE link flapping | pppoE interface uptime **11 h 03 m** at 21:24 MYT = re-dial at 10:21 MYT; **zero PPPoE counter resets** in 16 h of node-exporter | not flapping |
| PPP link-down events in the firewall log | `/api/diagnostics/log/ppp/ppp` returns **HTTP 200 with body `[]`** — this API key/endpoint yields nothing, so I could **not** check the link-event log. GUI → *Status → System Logs → PPP* is still unchecked. | **gap, unresolved** |
| pf state exhaustion | states **388 / 300 000 = 1.3 %** (peak 38 097 at 16:15) | ruled out |
| mbuf exhaustion | TCP `recvspace` peak **1 047 552 / 36 139 008 = 2.9 %**, steady state ~1.2 % | ruled out |
| CPU saturation on the firewall | peak **27.2 %** (20:53), typically 6–10 % | ruled out |
| MTU / MSS mismatch | PPPoE `pppoe0` MTU 1492; the WireGuard instance `ProtonVPN-ExitSingapore` sets **MTU 1420** (so `wg2` is 1420, not 1500 — corrected 26 Nov after reading `OPNsense/wireguard/server/servers`); **no `<mss>` anywhere**; PMTUD clean for DF-packets 64→1464 B | not a blackhole |
| Path-MTU blackhole | tested 64→1464-byte DF packets from a VLAN-31 pod — all pass | ruled out |
| Interface-level packet loss on the firewall NICs | no RX/TX errors as above | ruled out |
| Wrong gateway in use | `default 210.186.239.254 UGSSc wan` + `default 10.2.0.1 UGS opt12`, gateway status shows both "Online" | correct |

## One config observation to flag, not change silently

Three `<sysctl>` entries are set: **`net.route.netisr_maxqlen = 2048`** (default 256),
`kern.ipc.nmbclusters = 1`, `kern.ipc.nmbjumbop = 1`. Raising the netisr queue length is a
legitimate tuning knob and the numbers above show no mbuf/routing pressure, so I did **not**
attribute the 25 Nov fault to them — but `nmbclusters`/`nmbjumbop` at `1` is unusual and worth
confirming was intentional (OPNsense normally auto-sizes these).

## The ISP-side loss this file was originally written about (25 Nov, restored)

The first version of this file (2026-11-25) carried the hop-by-hop evidence, and I overwrote it in
error on 26 Nov while consolidating the gateway audit. Restoring the numbers here; the **ticket text
lives in `results/011-isp-not-home-devices.md`**, whose version supersedes the one that was here.

Measured 2026-11-25, 30 probes per hop:

| hop | address | loss | RTT |
|---|---|---|---|
| LAN | `192.168.1.1` | 0.0 % | 3 ms |
| **ISP gateway** | `210.186.239.254` (`isdn-tsk-239-254.tm.net.my`) | **12.5 %** | **135 ms** |
| Public | `8.8.8.8` | 12.5 % | 149 ms |

dpinger showed two episodes: 24 Nov 13:00–15:30 Z at 129–147 ms / 10–18 % loss, then ~11 h clean at
13–20 ms, then from 25 Nov 06:00 Z onward 125–159 ms / 0–10 % loss. Throughput swung between
940 Mbps and 2.5 Mbps in the same hour while upload held 455–623 Mbps — and 940/916 Mbps were
achieved at 114–130 ms RTT on two different servers, which is why "test-server luck" was rejected.

**26 Nov update:** the loss and latency are gone and the circuit is **back at full baseline** — the
in-cluster exporter logged **910–922 Mbps down / 521 Mbps up at 6.8 ms ping** overnight. (An interim
"62 % of baseline / possible rate cap" reading of mine was a Wi-Fi-vantage artifact; see
`results/014-post-recovery-speed-remeasured.md`.)

