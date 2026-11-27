parsed 5 rules from kubernetes/apps/observability/exporters/speedtest-exporter/app/prometheusrule.yaml

SpeedtestExporterAbsent   for: 0m
  expression under test (verbatim from the file):
    absent_over_time(up{job=~".*speedtest-exporter.*"}[130m])
    or
    max_over_time(up{job=~".*speedtest-exporter.*"}[130m]) == 0

  PASS healthy cluster -> EMPTY
  PASS target-gone arm -> ['1']
  info max_over_time(up[130m]) == 0 across all jobs -> 0 job(s) currently 0 (these are genuinely failing scrapes, arm2 is meant to catch them)

rest of the file:
  SpeedtestSlowInternetDownload      for=0m    -> not firing
  SpeedtestSlowInternetUpload        for=0m    -> not firing
  SpeedtestHighPingLatency           for=0m    -> not firing
  SpeedtestHighJitterLatency         for=0m    -> not firing

RESULT: PASS
