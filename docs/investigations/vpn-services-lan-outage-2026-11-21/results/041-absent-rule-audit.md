
====================================================================================================
1. #2604 coverage selectors - does each selector match a live series?
====================================================================================================
   (bare absent() on a selector that matches nothing = permanently-true critical alert)

   OK probe_success{service=...}       present=True  value=         0  (expected present=True)
        {"__name__": "probe_success", "instance": "1.1.1.1", "job": "probe/observability/vpn-icmp", "namespace": "observability", "service
        {"__name__": "probe_success", "instance": "https://one.one.one.one", "job": "probe/observability/vpn-http", "namespace": "observab
   OK wireguard peer {device="wg2"}    present=True  value=1795723639  (expected present=True)
        {"__name__": "opnsense_wireguard_peer_last_handshake_seconds", "device": "wg2", "device_name": "ProtonVPN-ExitSingapore", "device_
   OK up{job="opnsense-exporter"}      present=True  value=         1  (expected present=True)
        {"__name__": "up", "endpoint": "http", "instance": "10.69.0.68:8080", "job": "opnsense-exporter", "namespace": "observability", "p

   what labels the probe series really carry:
         1  {"__name__": "probe_success", "container": "blackbox-exporter", "endpoint": "http", "instance": "10.10.30.10", "job": "blackbox-exporte
         0  {"__name__": "probe_success", "instance": "1.1.1.1", "job": "probe/observability/vpn-icmp", "namespace": "observability", "service": "b
         1  {"__name__": "probe_success", "instance": "192.168.1.149", "job": "probe/observability/devices", "namespace": "observability", "service
         0  {"__name__": "probe_success", "instance": "gateway.cloudjur.com", "job": "probe/observability/devices", "namespace": "observability", "
         1  {"__name__": "probe_success", "instance": "http://192.168.1.149:8732/health", "job": "probe/observability/strix-halo-ai", "namespace": 
         1  {"__name__": "probe_success", "instance": "http://192.168.1.149:8743/health", "job": "probe/observability/strix-halo-ai", "namespace": 
         1  {"__name__": "probe_success", "instance": "http://192.168.1.149:8744/health", "job": "probe/observability/strix-halo-ai", "namespace": 
         0  {"__name__": "probe_success", "instance": "https://one.one.one.one", "job": "probe/observability/vpn-http", "namespace": "observability

====================================================================================================
2. The two coverage rules' current live state (already in 040 s6, restated with history)
====================================================================================================
   count_over_time(ALERTS{alertname="VpnEgressProbesAbsent"}[24h])
     (empty)
   count_over_time(ALERTS{alertname="VpnEgressTunnelAbsent"}[24h])
     (empty)
   ALERTS{alertname="VpnEgressProbesAbsent",alertstate="firing"}
     (empty)
   ALERTS{alertname="VpnEgressTunnelAbsent",alertstate="firing"}
     (empty)

====================================================================================================
3. Scrape interval per job (the number absent()+for: must be compared against)
====================================================================================================
   blackbox-exporter                  targets= 1 interval=30s path=/probe
   blackbox-exporter-vpn              targets= 1 interval=30s path=/metrics
   cert-manager                       targets= 1 interval=1m path=/metrics
   external-dns-opnsense-unbound      targets= 2 interval=30s path=/metrics
   node-exporter                      targets= 3 interval=30s path=/metrics
   nut-exporter                       targets= 1 interval=30s path=/ups_metrics
   opnsense-exporter                  targets= 1 interval=1m path=/metrics
   speedtest-exporter                 targets= 1 interval=1h path=/metrics

====================================================================================================
4. Replacement expression, three shapes
====================================================================================================
   arm1 = absent_over_time(up[130m])            -> target stopped producing samples
   arm2 = max_over_time(up[130m]) == 0          -> every scrape in the window failed

   healthy exporter (must be EMPTY):
     present=False  -> OK

   target gone entirely (must be 1):
     present=True value=1  -> OK

   arm2 alone against live data (must be EMPTY while up=1):
     present=False  -> OK

====================================================================================================
5. Sanity: the same arithmetic for the fast-scraped rules left alone
====================================================================================================
   OK absent_over_time(up{job="opnsense-exporter"}[10m])                     present=False
   OK absent_over_time(probe_success{job=~"probe/observability/vpn-.*"}[10m]) present=False
   OK absent_over_time(node_boot_time_seconds[10m])                          present=False
