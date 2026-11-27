
====================================================================================================
1. Are samples actually arriving? (count_over_time ignores the staleness lookback)
====================================================================================================
   count_over_time(up{job=~".*speedtest-exporter.*"}[24h])
                   24  {"endpoint": "metrics", "instance": "10.69.0.185:9798", "job": "speedtest-exporter", "namespace": "o
   min_over_time(up{job=~".*speedtest-exporter.*"}[24h])
                    1  {"endpoint": "metrics", "instance": "10.69.0.185:9798", "job": "speedtest-exporter", "namespace": "o
   max_over_time(up{job=~".*speedtest-exporter.*"}[24h])
                    1  {"endpoint": "metrics", "instance": "10.69.0.185:9798", "job": "speedtest-exporter", "namespace": "o
   count_over_time(speedtest_download_bits_per_second[24h])
                   24  {"endpoint": "metrics", "instance": "10.69.0.185:9798", "job": "speedtest-exporter", "namespace": "o
   count_over_time(speedtest_up[24h])
                   24  {"endpoint": "metrics", "instance": "10.69.0.185:9798", "job": "speedtest-exporter", "namespace": "o
   min_over_time(speedtest_up[24h])
                    1  {"endpoint": "metrics", "instance": "10.69.0.185:9798", "job": "speedtest-exporter", "namespace": "o

====================================================================================================
2. Exact sample times in the last 6h (60s step shows where the samples really land)
====================================================================================================
     11-26 14:31:40  up=1
     11-26 15:31:40  up=1
     11-26 16:31:40  up=1
     11-26 17:31:40  up=1
     11-26 18:31:40  up=1
     11-26 19:31:40  up=1

====================================================================================================
3. Current alert state and duty cycle over 24h
====================================================================================================
   ALERTS{alertname=~"Speedtest.*"}
                    1  {"__name__": "ALERTS", "alertname": "SpeedtestExporterAbsent", "alertstate": "pending", "severity": 
   count_over_time(ALERTS{alertname="SpeedtestExporterAbsent",alertstate="firing"}[24h])
     (empty - the expression yields no series right now)
   count_over_time(ALERTS{alertname="SpeedtestExporterAbsent",alertstate="pending"}[24h])
                 2640  {"alertname": "SpeedtestExporterAbsent", "alertstate": "pending", "severity": "critical"}
   count_over_time(ALERTS{alertname='Watchdog'}[24h])
                 2880  {"alertname": "Watchdog", "alertstate": "firing", "severity": "none"}

====================================================================================================
4. The fix, evaluated live: absent_over_time over >2 scrape intervals
====================================================================================================
   a window of 130m always contains at least two 60m-scrape samples, so it is empty while
   healthy and only turns 1 when the target has truly gone quiet.

   absent_over_time(up{job=~".*speedtest-exporter.*"}[130m])
     (empty - the expression yields no series right now)
   absent_over_time(up{job=~".*speedtest-exporter.*"}[65m])
     (empty - the expression yields no series right now)
   absent_over_time(speedtest_download_bits_per_second[130m])
     (empty - the expression yields no series right now)
   absent_over_time(speedtest_up[130m])
     (empty - the expression yields no series right now)
   absent_over_time(opnsense_gateways_status[10m])
     (empty - the expression yields no series right now)
   absent_over_time(probe_success{job=~'probe/observability/vpn-.*'}[90m])
     (empty - the expression yields no series right now)

====================================================================================================
5. Would the OTHER speedtest rules see data? (avg_over_time[4h] on 60m samples)
====================================================================================================
   avg_over_time(speedtest_download_bits_per_second{job=~".*speedtest-exporter.*"}[4h])
            909356500  {"endpoint": "metrics", "instance": "10.69.0.185:9798", "job": "speedtest-exporter", "namespace": "o
   avg_over_time(speedtest_upload_bits_per_second{job=~".*speedtest-exporter.*"}[4h])
            519100774  {"endpoint": "metrics", "instance": "10.69.0.185:9798", "job": "speedtest-exporter", "namespace": "o
   avg_over_time(speedtest_ping_latency_milliseconds{job=~".*speedtest-exporter.*"}[4h])
                7.255  {"endpoint": "metrics", "instance": "10.69.0.185:9798", "job": "speedtest-exporter", "namespace": "o

====================================================================================================
6. Rule health (step 039 crashed here: groups have no 'namespace' key)
====================================================================================================
   group keys sample: ['evaluationTime', 'file', 'interval', 'lastEvaluation', 'limit', 'name', 'rules']
   OpnsenseGatewayMonitoringDisabled health=ok      state=firing   for=-      interval=-
   OpnsenseServiceStopped           health=ok      state=firing   for=-      interval=-
   SpeedtestExporterAbsent          health=ok      state=pending  for=-      interval=-
   VolSyncVolumeOutOfSync           NOT DEPLOYED  <- correct, volsync rules are gone
   VpnEgressProbesAbsent            health=ok      state=inactive for=-      interval=-
   VpnProbeFailed                   health=ok      state=firing   for=-      interval=-
   VpnTunnelUpButNoReturn           health=ok      state=firing   for=-      interval=-
