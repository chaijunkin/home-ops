# 006 — Blast radius

## Real data loss, not a flaky probe

Per-pod rx over 3d @1h — `#` >1kB/s (real transfer), `.` >10 B/s, blank idle:

```
  slskd-0                  [##############################################..........................]
      last 8 hourly rx B/s: 322 321 321 306 318 319 319 307
  sabnzbd-57bf445f4c-nv4ng  [..............................................]
  shelfmark-7ddd65c4c6-wphwj[..............................................]
  metube-679647765-9lx52    [                                              ]
```

`slskd-0` (Soulseek, `media`) streamed >1kB/s for the first ~30 hourly samples and **flatlined at
the outage boundary**, holding ~320 B/s (keepalive-level) since. A real workload stopped
transferring at 08:31Z and has not recovered.

## Everything sharing the broken next hop

Pods with the `network/vpn` attachment — all of these have had no internet egress:

```
  default        changedetection-84bc995447-bz6tp    10.10.31.17/24
  downloads      metube-679647765-r86fn              10.10.31.15/24
  downloads      sabnzbd-57bf445f4c-7hvvv            10.10.31.11/24
  downloads      shelfmark-7ddd65c4c6-zcdgg          10.10.31.16/24
  media          slskd-0                             10.10.31.10/24
  observability  blackbox-exporter-vpn-5b467bf65b-79wkf  10.10.31.20/24
```

Also note the timing overlap with the 22 `KubeHpaMaxedOut` alerts (`metube`, `shelfmark`,
`tautulli`, …), which began in the same window. They may be collateral from the same event
rather than independent capacity problems — worth revisiting **after** egress is restored,
since maxed-out HPAs are the expected reaction when backlogged work cannot make progress.

## Unrelated

`KubeJobFailed` (4): `ai/ai-inference-smoke-test-*`, `renovate/chaijunkin-discovery-*`.
`Watchdog` (1): fires always by design. Neither is blackbox-related.
