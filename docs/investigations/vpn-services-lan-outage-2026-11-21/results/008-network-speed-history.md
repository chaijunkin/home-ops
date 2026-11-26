# Result 008 — Measured internet speed, and what the numbers really say

Ran `scripts/009-network-speed-check.sh` (plus `networkQuality`) on 2026-11-24 ~13:40–14:30 UTC.
Read-only; no cluster or firewall state changed.

## Headline

| Path | Download | Upload | Latency | Verdict |
|---|---|---|---|---|
| **WAN, wired (cluster, hourly automated, 7 d)** | **median 912 Mbps** (839–921) | **median 521 Mbps** (495–526) | **median 7.0 ms** (5.6–11.3) | **healthy** |
| **This Mac on Wi-Fi** (`networkQuality`, multi-stream) | 115 Mbps | 255 Mbps | idle 217 ms; under load 445 ms up / 630 ms down | **bottleneck is Wi-Fi** |
| Mac → gateway `192.168.1.1` (quiet link) | — | — | 9.3 / **20.4** / 54.2 ms | **poor for a LAN hop** |

So the ISP link is not the problem, and the VPN outage is not a bandwidth problem: the same
wire carried 912/521 Mbps with a 7 ms ping for the entire outage window.

The repo's own baseline comment (`# home is 300mbps` / `50mbps`) is badly stale — the link
measures ~912/521, i.e. a gigabit-class plan.

## The trap: two readings that were wrong before being fixed

1. **`speedtest_*` looked like it had "no data at all".** It is scraped every **60 m**
   (`servicemonitor.yaml`) and Prometheus' lookback delta is 5 m, so an instant query returns
   nothing for ~55 minutes of every hour. `up` for that job disappears for the same reason —
   which is *not* evidence of a dead exporter. Correct query: `last_over_time(<metric>[2h])`.
   A raw `query_range` on the metric name is also empty, for the same reason (steps miss samples).
2. **The exporter is healthy and was being scraped the whole time** —
   `health=up`, `lastError=''`, `lastScrape=2026-11-24T13:27:55`, pod IP = endpoint
   `10.69.0.185:9798` (unchanged; the `5 restarts (3d3h ago)` did not move the IP).

## Second trap: the test server changes, so the history is not comparable

| Sample | server id | ping | jitter | down | up |
|---|---|---|---|---|---|
| 7-day median (server **45623**) | 45623 | 7 ms | ~2.6 ms | **912 Mbps** | 521 Mbps |
| 2026-11-24 14:06 (during my own load) | 45623 | 132 ms | — | 108 Mbps | 470 Mbps |
| 2026-11-24 14:26 live request | **70564** | **126 ms** | **97.7 ms** | **1.55 Mbps** | 503 Mbps |

The exporter picks its own server. When it lands on a near one it reports 912 Mbps; when it
lands on a far/congested one it reports 1.5 Mbps. **Any 4 h-average speed alert over this metric
is therefore measuring server selection as much as the link.** Pinning the server id would make
the series usable as a trend.

Uplink stayed ~500–525 Mbps in every sample, including through a congested download — uplink
looks genuinely uncongested.

## Cloudflare specifically is slow from this ISP (both paths)

| Target | from Mac (Wi-Fi) | from cluster (wired, blackbox `module=icmp`) |
|---|---|---|
| `1.1.1.1` | 429 / **447** / 471 ms | 455 ms (success) |
| `1.0.0.1` | 432 / 452 / 468 ms | 475 ms (success) |
| `8.8.8.8` | 133 / 183 / 283 ms | 127 ms (success) |
| speedtest server | — | 7 ms |

Local/peered destinations are 7 ms, Google ~130–180 ms, Cloudflare ~450 ms — from *both* the
wired cluster and Wi-Fi, so it is the ISP's path to Cloudflare, not the Mac and not the cluster.
TCP was also slow to `1.1.1.1:443` from the Mac (`time_connect` 0.32–1.38 s, i.e. SYN
retransmits). Note the historical `17–26 ms` Cloudflare figure came from the **VPN-egress** probe
(`job=probe/observability/vpn-icmp`), which has been timing out at the 5 s limit since Nov 21 —
so there is no direct-path Cloudflare latency baseline in Prometheus to compare against.

## Bufferbloat, demonstrated by accident

At 14:06 the uplink was ~50 % busy with my own test traffic and the same cluster test that
normally reads 7 ms read **132 ms**, with responsiveness rated Low (445 ms up / 630 ms down).
That is queue build-up, not capacity. On a 912/521 Mbps link, AQM (CAKE/fq_codel) on the WAN is
worth enabling regardless of the VPN problem.

## Monitoring gaps found in `speedtest-exporter/app/prometheusrule.yaml`

1. `SpeedtestSlowInternetDownload`: `avg_over_time(speedtest_download_bits_per_second[4h]) < 200`
   compares **bits/s** to a **Mbps** number. It can only fire below 200 bit/s — effectively never.
   Needs `200e6`.
2. `SpeedtestSlowInternetUpload`: same bug, `< 30` instead of `30e6`.
3. `SpeedtestExporterAbsent`: `absent(up{job=~".*speedtest-exporter.*"} == 1)` with `for: 75m`.
   On a 60-minute scrape interval `up == 1` exists for seconds each hour, so the `for: 75m`
   pending window never completes → a *fully vanished* exporter never alerts. Needs
   `absent_over_time(up{...}[75m])` (or `absent(speedtest_up)` on a shorter window).
   Ironically the exporter that watches the internet has never been able to report that it is gone.
4. `scrapeTimeout: 1m` against a test that measured 60–90 s of wall time here — scrapes can
   legitimately hit the deadline, so `up` may flap independently of the link.

None of these were caused by the outage; they are pre-existing and were found while trying to
answer "what is my speed?".

## Bottom line

- Internet link: **fine** (~912/521 Mbps, 7 ms, stable all week).
- Mac's Wi-Fi: **the actual slowdown** (115 Mbps down, 20 ms to the gateway).
- Path to Cloudflare: **~450 ms from everything** — ISP-side, worth a ticket if it matters.
- Speed alerting: **three bugs**, all of which make an outage/slowdown invisible.
- The VPN outage remains exactly as diagnosed: confined to the WireGuard egress, not bandwidth.
