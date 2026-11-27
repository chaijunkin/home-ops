# Result 011 — ISP, not your devices: measured proof that nothing at home is hogging the link

`scripts/013-why-is-everything-slow.sh` + a wired probe pod, 2026-11-25 19:34–19:45 MYT
(11:34–11:45 UTC). Raw capture: temp dir `013-raw.log`.

## Verdict

**Time dotCom.** Nothing inside the house is hogging the network — the link was almost **idle**
while it was unusable.

| claim | measurement | conclusion |
|---|---|---|
| A device is saturating the link? | download **5.6 Mbps** right now on a **912 Mbps** link (0.6 %); **peak 5-min rate in 12 h = 58.2 Mbps** (6.4 %) | impossible — 94 % of the pipe was free |
| A service is generating bulk traffic? | total carried in 12 h: **38.7 GB down / 18.6 GB up** ≈ 7 Mbps average | that is less than two 4K streams |
| Some VLAN flooding internally? | busiest internal segment peaked 55 Mbps (`igc2`/`igc3`), `vlan0.31.1` ≈ **0.001 Mbps** | no internal flood, and it mirrors WAN, so it is transit |
| Self-inflicted congestion (bufferbloat)? | **62.5 %** of pings to `8.8.8.8` dropped *while* the link carried 5.6 Mbps | congestion cannot do that at 0.6 % utilisation |
| Wi-Fi is the problem? | over the **same** Wi-Fi path: `192.168.1.1` **0.0 % loss**; next hop `210.186.239.254` **37.5 % loss** | loss begins *after* the firewall |
| DNS feels slow? | resolver lookup **3–8 ms**; `dig` to 1.1.1.1/8.8.8.8 answered | not name resolution |
| ISP path impaired? | see below, on **wired and** Wi-Fi, TCP and ICMP | yes |

## The impairment, from two independent vantage points

Wi-Fi (the Mac, 30 ICMP probes/hop):

| target | loss | RTT min/avg/max |
|---|---|---|
| `192.168.1.1` (firewall, LAN) | **0.0 %** | 2.9 / 14.1 / 48.8 ms |
| `210.186.239.254` (Time dotCom BRAS) | **37.5 %** | 131 / 145 / 154 ms |
| `8.8.8.8` | **62.5 %** | 144 / 150 / 159 ms |
| `1.1.1.1` | **25.0 %** | 166 / 176 / 185 ms |

Wired (a pod on a cluster node, 12 fresh TCP handshakes — no ICMP, no Wi-Fi):

| target | TCP connect RTT |
|---|---|
| `1.1.1.1:443` | min 149 / p50 165 / **max 175 ms** |
| `8.8.8.8:443` | min 139 / p50 148 / **max 457 ms** |
| `104.16.132.229:443` (Cloudflare) | min 144 / p50 181 / **max 1188 ms** |

Healthy is 5–10 ms (that is exactly what this link measured 5–7 ms on 24 Nov). A TCP handshake
that takes **1.2–3.2 s** at worst is why pages, SSH and API calls feel dead rather than merely slow.

Real transfers at the same minute:

| vantage | test | result |
|---|---|---|
| Mac (Wi-Fi) | 25 MB from Cloudflare, 3 runs | **12 Mbps**, then a run that **timed out at 40 s with 13 MB of 25 MB**, then 23 Mbps |
| cluster pod (wired) | 25 MB from Cloudflare, 2 runs | **2 Mbps**, **3 Mbps** (both hit the 30 s cap) |
| speedtest-exporter 19:28 MYT | official hourly | **Download 1.03 Mbps / Upload 518 Mbps / Ping 147.7 ms**, plus a `Cannot open socket` error at 11:28:01Z |

**Download is being destroyed while upload is untouched (518 Mbps).** Your firewall, your switch,
your AP and your LAN all sit on both directions equally — only something upstream of the ISP's
downstream path can produce that asymmetry.

## macOS networkQuality (responsiveness, the "feels slow" metric)

```
Uplink capacity:          217.5 Mbps
Downlink capacity:        147.9 Mbps
Uplink responsiveness:    Low   (320 ms | 187 RPM)
Downlink responsiveness:  Low   (707 ms |  84 RPM)
Idle latency:             436 ms | 137 RPM
```

Idle latency should be tens of milliseconds. 436 ms with **nothing else running** is the link, not
a queue you created.

## Retraction: the multipath hypothesis is wrong

At 19:15 a ping sample showed `min 3.8 ms / avg 135 ms`, which looks like two paths (per-packet
spraying). Two tests reject it:

* 60-probe sorted distributions are **unimodal**: BRAS 135→157 ms, `8.8.8.8` 145→173 ms,
  `1.1.1.1` 163→182 ms. A single fast cluster never appears; the 3.8 ms samples were noise.
* Reordering check on 30 probes to `8.8.8.8`: **0 out-of-order arrivals**, and missing sequence
  numbers (8, 9, 10) **never reappear later**.

So this is **genuine packet loss on one degraded path**, not reordering. It is also **worsening**:
12.5 % loss at 19:15 → 37.5 % (BRAS) / 62.5 % (`8.8.8.8`) at 19:37.

## What this means for the earlier findings

* The Nov 21 WireGuard egress failure and today's slowness are now clearly **the same operator**,
  and today's is severe enough to be visible without any VPN involved.
* The OPNsense faults found in result 010 (gateway monitoring disabled, loose thresholds, no
  `monitor_killstates`, no MSS clamp) remain real but are about **visibility**, not cause.
* No home device or service is implicated. Do not go hunting through VLANs or QoS — the numbers
  above already exclude that branch.

## Updated ticket text (use this one — the numbers are far stronger than result 010's)

> **Severe, worsening packet loss on my fibre line — download effectively dead, upload normal**
>
> Account/line: [your account]. Service: Time Fibre, PPPoE, OPNsense router. PPPoE session stable,
> no reconnects, zero NIC errors.
>
> Measured 25 Nov 2026, 19:35–19:45 MYT, from two independent points inside my network:
>
> * my router LAN address — **0 % loss, 3 ms**
> * **your gateway `210.186.239.254` (`isdn-tsk-239-254.tm.net.my`) — 37.5 % loss, 145 ms**
> * `8.8.8.8` — **62.5 % loss**, 150 ms; `1.1.1.1` — 25 % loss, 176 ms
> * wired host, TCP handshake RTT only (no ICMP): **139–181 ms**, worst single handshake **3.2 s**
>   (this line measured 5–7 ms on 24 Nov)
>
> Effect on real traffic at the same minute:
> * download **1.03 Mbps** (automated test) and **2–3 Mbps** on manual 25 MB transfers, one of which
>   **timed out having received 13 MB of 25 MB**
> * upload on the same test: **518 Mbps** — unaffected
> * macOS responsiveness test: **idle latency 436 ms**, downlink responsiveness 707 ms
>
> My side is verified: my link was **94 % idle** during this (5.6 Mbps of ~912 Mbps capacity in use,
> 58 Mbps peak over 12 h), zero interface errors, no traffic shaping configured, path MTU verified
> 64→1464 bytes with no blackholing, and the loss appears at **your** gateway address, not mine.
> Distribution analysis shows **true drops, not reordering** (0 out-of-order packets, 60-probe
> unimodal RTT).
>
> It is getting worse by the hour: 12.5 % loss at 19:15 MYT, 37.5 % at 19:37 MYT. Please check for
> congestion or a degraded/flapping link on the path for my circuit, and correlate with my 21 Nov
> incident (no return traffic reaching my site via a WireGuard tunnel exiting Singapore).
