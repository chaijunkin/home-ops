# Result 012 — What the firewall's GUI/API/logs/traffic actually show (coverage + gaps closed)

`scripts/014-opnsense-live-log-and-traffic.sh`, 2026-11-25 20:16–20:24 MYT (12:16–12:24 UTC).

## Coverage: exactly what has and has not been inspected

| channel | inspected? | how / limitation |
|---|---|---|
| **OPNsense GUI** | **no, never** | no credentials used and I don't drive the web UI. Everything below is the same data the GUI pages render, read from the API instead. |
| **API — config** | **yes, completely** | `GET /api/core/backup/download/this` → the live 312,402-byte `config.xml`. Parsed: gateways (`OPNsense/Gateways/gateway_item`), gateway groups (`load_balancer`), policy routes, static routes, VIP/CARP, PPPoE/WAN, Unbound/DNS, shaper/altq/dnshaper, all 38 sysctl entries, offload flags, `<mss>`. Result 010. |
| **API — runtime gateway state** | **yes, repeatedly** | `GET /api/routes/gateway/status` (dpinger). Also `diagnostics/interface/getInterfaceNames`. |
| **API — live firewall log** | **yes, now** (result 010 could not) | `GET /api/diagnostics/firewall/log?rowCount=400` → 826 KB, **1000 rows spanning 20:15:20→20:16:55 (95 s)**. |
| **Live traffic — counters** | yes | node-exporter per-NIC rates/errors on the firewall, plus active probes from Wi-Fi and wired. |
| **Live traffic — per connection** | **no** | `diagnostics/firewall/getStatesSummary`, `getStateCount`, `dump`, `firewall/statistics/show`, `diagnostics/interface/getInterfaceTraffic/*`, `getInterfaceRates*`, `getARPTable`, `getSystemInfo` → **all 404** with this API key. |
| **Flow history (NetFlow/IPFIX)** | **no** | no `os-velociraptor`/NetFlow plugin configured → there is no per-flow history to query, ever. |
| **System / PPP / route logs** | **no** | `/api/diagnostics/log/{system,ppp,routenotification}/*` return **HTTP 200 with body `[]`** on GET — the GUI reads them with POST. Not attempted (POST-only session, kept GET-only). GUI check takes 10 s: *Status → System Logs → PPP / System*. |

## What the live firewall log proves

1000 packets in 95 seconds:

* **936 pass, 64 block.** Every single block is `rule 13 — "Default deny / state violation rule"`.
* **Zero blocks of outbound/return traffic** — no drop of your browsing, DNS or downloads by the
  firewall. Split: 8 blocks on `pppoe0` are **inbound** unsolicited packets from random internet
  hosts (`111.206.174.2`, `135.233.115.176`, `212.73.148.42`, `195.182.16.23`) to your public IP
  **`210.186.239.63`** — ordinary internet scanning, correctly denied.
* 56 blocks are `10.10.32.2/.3/.4/.5 → 16.163.195.33:9999` plus a few NTP (`:123`) attempts on
  `vlan0.32.1`. That is a **separate, unrelated policy gap**: those VLAN-32 pods have no allow rule
  for that endpoint and are retrying. Worth fixing, irrelevant to the slowness.
* WAN traffic mix in that window: `1.1.1.1:53` (151), HTTPS to Cloudflare/GitHub, `1.0.0.1:853`
  (DoT), and `37.19.201.130:51820` (15 = WireGuard keepalive handshakes, consistent with the tunnel
  being alive but carrying no user traffic). Protocols: 565 tcp / 407 udp / 28 icmp.
* **No `block` from bogons**: `filter/blockpriv` and `filter/blockbogons` are **not set**, i.e.
  bogon blocking is not even enabled — a security observation, not a cause of loss.

## dpinger, current window (20:17 MYT)

```
WAN_PPPOE               address 210.186.239.254  status none  loss ~  delay ~  monitor ~  "Online"
WAN_ProtonVPNSingapore  address 10.2.0.1         status none  loss 10.0 %  delay 148.7 ms  "Online"
```

WAN monitoring still off (`~`), and the VPN-facing monitor still says **10 % loss / 148.7 ms**.

## Sustained recorder (`scripts/015-loss-recorder.sh`, 8 rounds, 12 s apart, 20:20–20:24 MYT)

| UTC | LAN % | BRAS % | BRAS ms | 8.8.8.8 % | 8.8.8.8 ms | 1.1.1.1 % | 1.1.1.1 ms | DL Mbps |
|---|---|---|---|---|---|---|---|---|
| 12:20:32 | 0 | 0 | 151.5 | 66.7 | 144.4 | 16.7 | 166.1 | 10.2 |
| 12:21:03 | 0 | 0 | 144.9 | 0 | 146.8 | 0 | 168.4 | 8.3 |
| 12:21:33 | 0 | 0 | 144.4 | 40.0 | 150.0 | 20.0 | 162.7 | 13.1 |
| 12:22:04 | 0 | 0 | 139.2 | 20.0 | 144.0 | 20.0 | 173.5 | 7.5 |
| 12:22:35 | 0 | 0 | 138.7 | 40.0 | 141.7 | 0 | 175.9 | 9.9 |
| 12:23:06 | 0 | 0 | 138.0 | 40.0 | 146.1 | 20.0 | 167.7 | 8.2 |
| 12:23:35 | 0 | 20.0 | 136.3 | 0 | 147.4 | 20.0 | 167.6 | 15.6 |
| 12:24:06 | 0 | 0 | 140.6 | 0 | 141.2 | 0 | 163.4 | 2.3 |

Summary: LAN **0.0 % loss in every round**; BRAS latency **136–152 ms (avg 141.7)**; public loss
bursts to **66.7 %**; real downloads **2.3–15.6 Mbps**.

**The most diagnostic line is the latency, not the loss.** `210.186.239.254` is the ISP's own
CPE-facing gateway: it should answer in 1–5 ms. It answers in **141 ms constantly, even in the
rounds with zero packet loss.** Nothing in a house — no device, no Wi-Fi, no download — can add
140 ms to the ISP's own gateway address while leaving the LAN side at 4 ms and 0 % loss.

## Reading for the ISP call

Loss is bursty, latency is not. That combination points at the access/aggregation path (ONT optics,
a flapping uplink, or a congested BRAS) rather than at a queue your traffic created — consistent
with the earlier proof that the link was only 0.6 % utilised while unusable.
