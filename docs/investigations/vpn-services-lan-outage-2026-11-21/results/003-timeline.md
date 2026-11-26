# 003 — Outage timeline

## Probe transition points (5m step, 3d window)

```
  probe/observability/vpn-icmp  1.1.1.1
    UP->DOWN @ 2026-11-19 12:26:07Z   DOWN->UP @ 2026-11-19 12:31:07Z
    UP->DOWN @ 2026-11-19 14:06:07Z   DOWN->UP @ 2026-11-19 14:11:07Z
    UP->DOWN @ 2026-11-19 14:21:07Z   DOWN->UP @ 2026-11-19 14:26:07Z
    UP->DOWN @ 2026-11-20 14:21:07Z   DOWN->UP @ 2026-11-20 14:26:07Z
    UP->DOWN @ 2026-11-21 08:31:07Z   (no recovery)

  probe/observability/vpn-http  https://one.one.one.one
    UP->DOWN @ 2026-11-21 08:31:07Z   (no recovery)
```

Continuous for ~26h at capture. The earlier 5-minute blips self-recovered; this one never has.

## Everything rebooted together

```
node_boot_time_seconds (UTC)
  gateway.cloudjur.com:9100    2026-11-21 09:50:45
  10.10.30.10:9100             2026-11-21 10:03:01
  k8s-0                        2026-11-21 10:04:42
```

Firewall reachability over 3d (30m step, one `X`):

```
    ...........................................................................................X...................................................
    down samples: ['11-21 08:37']
```

Blackbox-vpn container death:

```
restartCount: 2
lastState.terminated: { exitCode: 255, reason: "Unknown", finishedAt: "2026-11-21T10:05:01Z" }
```

`exitCode 255 / reason Unknown` is a runtime/node-level kill, not an application crash.

## Sequence

| UTC | event |
|---|---|
| 08:31:07 | both VPN probes go 0 — **outage begins** |
| 08:37 | firewall node-exporter unreachable — the firewall itself went dark |
| 09:50:45 | gateway boot time — OPNsense rebooted |
| 10:03:01 / 10:04:42 | second infra host and `k8s-0` boot |
| 10:05:01 | blackbox-vpn container killed (255/Unknown) |
| 10:13 / 10:22 | Alertmanager `startsAt` |

Two things this settles:

1. **The reboot is not the root cause.** The outage began ~1.5h *before* the reboot and the
   reboot did not clear it.
2. **The alert `startsAt` lags the metric by ~1h40m** because Prometheus itself restarted
   through the event and lost its pending-state, re-deriving `startsAt` afterwards. Do not use
   `startsAt` as the incident start; the metric says 08:31Z.

No GitOps commits landed in the window — so this was not a change from this repository:

```
$ git log --since=2026-11-19 --until=2026-11-23   # (empty)
```

Pattern is an infrastructure/power event spanning the firewall and both infra hosts.
