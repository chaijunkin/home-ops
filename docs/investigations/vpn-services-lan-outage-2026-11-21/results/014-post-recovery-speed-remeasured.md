# Result 014 — 26 Nov: the circuit is healthy at baseline; my "throughput cap" reading was wrong

`scripts/022-sustained-load-ladder.sh` + the speedtest-exporter's own results, 2026-11-26 08:26–09:00 MYT.

## Verdict

**The circuit is back to full baseline.** Measured by the in-cluster speedtest exporter, hourly,
unattended — the most trustworthy vantage point available:

| time (MYT) | ping | download | upload |
|---|---|---|---|
| 25 Nov 22:28 | 231.98 ms | **2.23 Mbps** | 497.88 Mbps |
| 25 Nov 23:28 | 128.12 ms | 901.28 Mbps | 535.65 Mbps |
| 26 Nov 00:28 | 5.71 ms | 914.20 Mbps | 521.04 Mbps |
| 26 Nov 01:28 | 7.98 ms | 916.85 Mbps | 520.61 Mbps |
| 26 Nov 04:28 | 6.90 ms | 910.68 Mbps | 522.25 Mbps |
| 26 Nov 07:28 | 6.94 ms | 917.21 Mbps | 520.54 Mbps |
| 26 Nov 08:28 | 6.80 ms | **922.32 Mbps** | 521.06 Mbps |

The 25 Nov impairment (2.23 Mbps, 232 ms ping) ended between 23:28 and 00:28 MYT. Everything since is
at the 912 / 521 baseline with single-digit ping. Corroborated from the Mac: ISP gateway
`210.186.239.254` **8–9 ms / 0 % loss** (was 136–152 ms / up to 37.5 %), `8.8.8.8` 14–15 ms / 0 %.

**There is no rate cap and no re-homed-PPPoE problem.** I wrote an earlier version of this file
claiming throughput was stuck at 62–66 % of baseline. That was wrong, and the reasons are worth
recording because they are the classic way a speed investigation goes sideways.

## Four measurement errors of mine, all found and corrected

Each of these could have become a false conclusion, and two of them had already been written into
this file or into a result document.

1. **Vantage point.** Every number I quote for "your speed" came from **this Mac, over Wi-Fi**:
   single-stream 334–387 Mbps, 3 concurrent streams 566 Mbps, 2 uploads 344 Mbps. The wired
   in-cluster exporter gets **910–922 Mbps** at the same moment. The shortfall was the Mac's own
   Wi-Fi link, not the circuit. Lesson: measure throughput from a wired host or the exporter, never
   from a Wi-Fi laptop, and compare like-for-like vantage points before declaring a regression.
2. **Double unit conversion.** `speedtest_download_bits_per_second` is already bit/s, so
   `916540000` **is** 916.54 Mbps. I multiplied by 8 again and printed "7332 Mbps". This is also why
   the current rules' thresholds (`< 200`, `< 30`) are dead: they are comparing bit/s against a
   number that only makes sense as Mbps. Correct thresholds are `200e6` / `30e6`.
3. **Endpoint artifact.** `speed.cloudflare.com/__down?bytes=100000000` returns **HTTP 403** — the
   endpoint caps `bytes` just under 100 MB. `bytes=99000000` → HTTP 200 at 387 Mbps. So the
   "`0 Mbps`, 1 byte received" rows in the ladder below mean "the CDN refused the request".
   Cross-check that behaved normally: `proof.ovh.net/files/100Mb.dat` → HTTP 200, 95 Mbps (far server).
   The 25 Nov conclusions still stand because those samples used 2–8 MB requests.
4. **My own parser.** The parallel-run summariser printed "SUM = 0 Mbps" for a healthy test:
   `curl -w` writes `  stream1: 30773633` and I did `float(whole file)`. Re-parsed correctly it was
   246 + 107 + 213 = 566 Mbps (over Wi-Fi, see 1).

## What the ladder did establish (still valid, as a *latency* result)

```
size        round  Mbps(over Wi-Fi)  complete?  LAN       ISP-bras   google     cloudflare
10 MB       1      245               yes        0.0%/4ms  0.0%/8ms   0.0%/14ms  0.0%/19ms
25 MB       1–2    334 / 317         yes        0.0%/5ms  0.0%/8ms   0.0%/14ms  0.0%/19ms
50 MB       1–2    277 / 407         yes        0.0%/5ms  0.0%/9ms   0.0%/15ms  0.0%/19ms
100 MB      1–2    0                 403        0.0%/5ms  0.0%/8ms   0.0%/14ms  0.0%/19ms
200 MB      1–2    0                 403        0.0%/5ms  0.0%/9ms   0.0%/15ms  0.0%/19ms
```

Zero loss everywhere and 8–9 ms to the ISP gateway under load — the access path is clean even while
saturated. That is the useful part of this run.

## The scrape-cadence trap that also needed clearing

`speedtest_*` is scraped **hourly** (`interval: 60m` in `servicemonitor.yaml`), so an instant query
returns "no data" for ~55 minutes of every hour and only 3 samples exist in a 3-hour range window:

```
06:32  916540000 bit/s
07:32  917207696 bit/s
08:32  922324560 bit/s
```

That staleness is why `SpeedtestExporterAbsent` uses `for: 75m` — deliberately longer than the 60 m
scrape interval, so a normal gap doesn't page. **I had recorded that this rule "can never fire"; that
is wrong** — it fires when 75 consecutive minutes pass with no successful scrape, which is exactly
the intent. It stays as it is. The rules that genuinely cannot fire are only the two threshold ones.
