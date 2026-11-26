# 001 — Firing alerts

Captured 2026-11-22 ~11:00 UTC via Alertmanager `/api/v2/alerts`.

```
  2  BlackboxProbeFailed          critical
 22  KubeHpaMaxedOut              warning
  4  KubeJobFailed                warning
  2  VpnProbeFailed               critical
  1  Watchdog                     none
total active: 31
```

The two blackbox alerts, both `critical`, both receivers `discord` + `pushover`:

```
BlackboxProbeFailed | probe/observability/vpn-icmp | 1.1.1.1               | blackbox-exporter-vpn | starts 2026-11-21T10:13:12Z
VpnProbeFailed      | probe/observability/vpn-http | https://one.one.one.one | blackbox-exporter-vpn | starts 2026-11-21T10:22:29Z
```

Rule (`kubernetes/apps/observability/exporters/blackbox-exporter/vpn/helmrelease.yaml:51`):

```yaml
- alert: VpnProbeFailed
  expr: probe_success{service="blackbox-exporter-vpn"} == 0
  for: 15m
  labels: {severity: critical}
```

Both fire on the **VPN** exporter only. No alert on the regular `blackbox-exporter`.

## Red herring eliminated

`blackbox-exporter-7cc867c9d5-9tlp2` shows `0/1 Completed`, `DisruptionTarget=True`, terminated
2026-11-06 exit 0 with no events. It is a 16-day-old drain leftover, not serving traffic:

```
NAME                    READY   UP-TO-DATE   AVAILABLE
blackbox-exporter       1/1     1            1
blackbox-exporter-vpn   1/1     1            1
```

## Unrelated, kept separate

`KubeHpaMaxedOut` (22) and `KubeJobFailed` (4: `ai/ai-inference-smoke-test-*`,
`renovate/chaijunkin-discovery-*`). `Watchdog` always fires by design. None are blackbox.
