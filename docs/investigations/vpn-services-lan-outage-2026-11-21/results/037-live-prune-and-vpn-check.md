====================================================================================================
1. PR #2608 state
====================================================================================================
    state=MERGED merged=2026-11-26T19:30:28Z commit=1376817d2 mergeState=UNKNOWN

====================================================================================================
2. Objects #2608 will prune (should still be Present until it merges)
====================================================================================================
  namespace volsync-system:
    volsync-system   Active   166d
  its contents:
    serviceaccount/default   166d
  remediation webhook deployment:
    Error from server (NotFound): deployments.apps "remediation-webhook" not found
  remediation cronjob:
    Error from server (NotFound): cronjobs.batch "remediation" not found
  the live snapshot-controller that MUST survive:
    snapshot-controller   1/1   1     1     117d
  volsync CRDs (still expected - deletion is a separate decision):
    kopiamaintenances.volsync.backube                                             2026-06-13T19:14:39Z
    replicationdestinations.volsync.backube                                       2026-06-13T19:14:39Z
    replicationsources.volsync.backube                                            2026-06-13T19:14:39Z
  volsync CRs anywhere (must stay 0):
    No resources found
  Flux app Kustomizations naming volsync/webhook/remediation (should vanish after merge):
    none

====================================================================================================
3. VPN egress: is Proton still not forwarding?
====================================================================================================
  VPN probe success (0 = VLAN31 egress dead):
  all probe targets by job:
                 1  {'instance': '10.69.0.216:9115', 'job': 'blackbox-exporter-vpn'}
                 1  {'instance': '10.69.0.24:9115', 'job': 'blackbox-exporter'}
                 1  {'instance': '10.69.0.68:8080', 'job': 'opnsense-exporter'}
  wireguard handshake age in seconds (wg2 = egress tunnel):
     1795722765.78  {'device': 'wg1', 'instance': '10.69.0.68:8080', 'job': 'opnsense-exporter', 'peer_name': 'Home_JK'}
     1795722765.78  {'device': 'wg1', 'instance': '10.69.0.68:8080', 'job': 'opnsense-exporter', 'peer_name': 'Home_Wireguard_Family_Shared'}
    90.77999997138977  {'device': 'wg2', 'instance': '10.69.0.68:8080', 'job': 'opnsense-exporter', 'peer_name': 'ProtonVPN_Singapore'}
  wireguard peer status:
                 0  {'device': 'wg1', 'instance': '10.69.0.68:8080', 'job': 'opnsense-exporter', 'peer_name': 'Home_JK'}
                 0  {'device': 'wg1', 'instance': '10.69.0.68:8080', 'job': 'opnsense-exporter', 'peer_name': 'Home_Wireguard_Family_Shared'}
                 1  {'device': 'wg2', 'instance': '10.69.0.68:8080', 'job': 'opnsense-exporter', 'peer_name': 'ProtonVPN_Singapore'}
  interface status for wg1/wg2:
  gateway status / loss:
                 1  {'instance': '10.69.0.68:8080', 'job': 'opnsense-exporter', 'name': 'WAN_ProtonVPNSingapore'}
  gateway monitoring enabled (0 = dpinger off, the WAN_PPPOE to-do):
                 1  {'instance': '10.69.0.68:8080', 'job': 'opnsense-exporter', 'name': 'WAN_ProtonVPNSingapore'}
                 0  {'instance': '10.69.0.68:8080', 'job': 'opnsense-exporter', 'name': 'WAN_PPPOE'}

====================================================================================================
4. Alert state (firing + pending)
====================================================================================================
  firing by name:
                 2  {'alertname': 'BlackboxProbeFailed'}
                22  {'alertname': 'KubeHpaMaxedOut'}
                 4  {'alertname': 'KubeJobFailed'}
                 1  {'alertname': 'OpnsenseGatewayMonitoringDisabled'}
                 1  {'alertname': 'OpnsenseServiceStopped'}
                 2  {'alertname': 'VpnProbeFailed'}
                 1  {'alertname': 'VpnTunnelUpButNoReturn'}
                 1  {'alertname': 'Watchdog'}
  VPN/backup/gateway/watchdog rules specifically:
                 1  {'alertname': 'BlackboxProbeFailed', 'instance': '1.1.1.1', 'job': 'probe/observability/vpn-icmp', 'severity': 'critical'}
                 1  {'alertname': 'BlackboxProbeFailed', 'instance': 'https://one.one.one.one', 'job': 'probe/observability/vpn-http', 'severity': 'critical'}
                 1  {'alertname': 'OpnsenseGatewayMonitoringDisabled', 'instance': '10.69.0.68:8080', 'job': 'opnsense-exporter', 'name': 'WAN_PPPOE', 'severity': 'warning'}
                 1  {'alertname': 'OpnsenseServiceStopped', 'instance': '10.69.0.68:8080', 'job': 'opnsense-exporter', 'name': 'crowdsec', 'severity': 'warning'}
                 1  {'alertname': 'SpeedtestExporterAbsent', 'severity': 'critical'}
                 1  {'alertname': 'VpnProbeFailed', 'instance': '1.1.1.1', 'job': 'probe/observability/vpn-icmp', 'severity': 'critical'}
                 1  {'alertname': 'VpnProbeFailed', 'instance': 'https://one.one.one.one', 'job': 'probe/observability/vpn-http', 'severity': 'critical'}
                 1  {'alertname': 'VpnTunnelUpButNoReturn', 'device': 'wg2', 'instance': '10.69.0.68:8080', 'job': 'opnsense-exporter', 'peer_name': 'ProtonVPN_Singapore', 'severity': 'critical'}
                 1  {'alertname': 'Watchdog', 'severity': 'none'}
  rule health for the rules #2604/#2607 shipped + the deleted VolSyncVolumeOutOfSync:
    (rules endpoint unreachable)
