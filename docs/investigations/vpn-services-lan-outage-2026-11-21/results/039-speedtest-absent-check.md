
====================================================================================================
1. Every speedtest* series Prometheus has right now
====================================================================================================
   /api/v1/series -> 0 distinct names: []
   __name__ enumeration (label values):
     ['speedtest_download_bits_per_second', 'speedtest_jitter_latency_milliseconds', 'speedtest_ping_latency_milliseconds', 'speedtest_server_id', 'speedtest_up', 'speedtest_upload_bits_per_second']

====================================================================================================
2. The rule as deployed vs what the exporter actually serves
====================================================================================================
   instant queries:
   count({__name__=~"speedtest.*"})
     (no series)
   absent(speedtest_download_bits_per_second)
                    1  {}
   up{job="speedtest-exporter"}
     (no series)
   timestamp(up{job="speedtest-exporter"})
     (no series)

====================================================================================================
3. Did the series exist earlier today? (5-day range, presence per 6h)
====================================================================================================
   (no range data - the metric family has not existed in the last 5 days)

====================================================================================================
4. What the exporter serves directly (no Prometheus in the path)
====================================================================================================
   pod log line format + last 3 tests already captured in step 037 output.
   scrapeUrl          = http://10.69.0.185:9798/metrics
   lastScrape         = 2026-11-26T19:27:55.483062097Z
   lastScrapeDuration = 22.632570275
   lastValue          = None
   labels             = {"endpoint": "metrics", "instance": "10.69.0.185:9798", "job": "speedtest-exporter", "namespace": "observability", "pod": "speedtest-exporter-7cbd98c67b-7n98v", "service": "speedtest-exporter"}

====================================================================================================
5. Which jobs are failing (KubeJobFailed x4)
====================================================================================================
   kube_job_status_failed == 1
                    1  {"__name__": "kube_job_status_failed", "container": "kube-state-metrics", "endpoint": "http", "instance": "10.69.0.43:80
                    1  {"__name__": "kube_job_status_failed", "container": "kube-state-metrics", "endpoint": "http", "instance": "10.69.0.43:80
                    1  {"__name__": "kube_job_status_failed", "container": "kube-state-metrics", "endpoint": "http", "instance": "10.69.0.43:80
                    1  {"__name__": "kube_job_status_failed", "container": "kube-state-metrics", "endpoint": "http", "instance": "10.69.0.43:80
   kube_job_failed == 1
                    1  {"__name__": "kube_job_failed", "condition": "true", "container": "kube-state-metrics", "endpoint": "http", "instance": 
                    1  {"__name__": "kube_job_failed", "condition": "true", "container": "kube-state-metrics", "endpoint": "http", "instance": 
                    1  {"__name__": "kube_job_failed", "condition": "true", "container": "kube-state-metrics", "endpoint": "http", "instance": 
                    1  {"__name__": "kube_job_failed", "condition": "true", "container": "kube-state-metrics", "endpoint": "http", "instance": 
   max by (namespace,job_name) (kube_job_status_failed)
                    0  {"job_name": "ai-inference-smoke-test-29890080", "namespace": "ai"}
                    0  {"job_name": "ai-inference-smoke-test-29890440", "namespace": "ai"}
                    1  {"job_name": "ai-inference-smoke-test-29927880", "namespace": "ai"}
                    1  {"job_name": "ai-inference-smoke-test-29928240", "namespace": "ai"}
                    1  {"job_name": "ai-inference-smoke-test-29928600", "namespace": "ai"}
                    0  {"job_name": "atuin-20261126190014", "namespace": "default"}
                    0  {"job_name": "autobangumi-remote-20261126193855", "namespace": "downloads"}
                    0  {"job_name": "bazarr-20261126192112", "namespace": "downloads"}
                    0  {"job_name": "bazarr-remote-20261126191637", "namespace": "downloads"}
                    0  {"job_name": "chaijunkin-chaijunkin-charts-mirror-1bbee3152p8jt", "namespace": "renovate"}
                    0  {"job_name": "chaijunkin-chaijunkin-containers-861180c8xfbtz", "namespace": "renovate"}
                    0  {"job_name": "chaijunkin-chaijunkin-home-ops-bef49f15dd98r", "namespace": "renovate"}
                    1  {"job_name": "chaijunkin-discovery-6de9ae35b4t77", "namespace": "renovate"}
                    0  {"job_name": "cilium-install", "namespace": "kube-system"}
                    0  {"job_name": "convertx-20261126185827", "namespace": "default"}
                    0  {"job_name": "filebrowser-20261126192445", "namespace": "media"}
                    0  {"job_name": "hermes-remote-20261126192730", "namespace": "ai"}
                    0  {"job_name": "jellyfin-20261126192742", "namespace": "media"}
                    0  {"job_name": "kometa-29928480", "namespace": "media"}
                    0  {"job_name": "kritika-run-341d1e61", "namespace": "dev"}
                    0  {"job_name": "kyverno-migrate-resources", "namespace": "security"}
                    0  {"job_name": "lidarr-20261126193704", "namespace": "downloads"}
                    0  {"job_name": "mealie-remote-20261126195409", "namespace": "default"}
                    0  {"job_name": "memini-fsck-29927820", "namespace": "ai"}
                    0  {"job_name": "nas-f-1795722165", "namespace": "storage"}
                    0  {"job_name": "open-webui-remote-20261126192626", "namespace": "ai"}
                    0  {"job_name": "opnsense-backup-29927520", "namespace": "jobs"}
                    0  {"job_name": "picoshare-20261126190625", "namespace": "default"}
                    0  {"job_name": "plex-20261126190042", "namespace": "media"}
                    0  {"job_name": "prowlarr-20261126192408", "namespace": "downloads"}
                    0  {"job_name": "rclone-b2-vw-to-local-29927520", "namespace": "storage"}
                    0  {"job_name": "rclone-r2-tf-to-local-29927520", "namespace": "storage"}
                    0  {"job_name": "remote-f-1795721205", "namespace": "storage"}
                    0  {"job_name": "snapdel-nas-e832f819-e0f5b949-f437-4e1e-95a5-6dccd62daf9c", "namespace": "storage"}
                    0  {"job_name": "snapdel-remote-65029913-f36df843-8a76-46-e5cc1839e8e67236", "namespace": "storage"}
                    0  {"job_name": "sonarr-20261126193452", "namespace": "downloads"}
                    0  {"job_name": "sparkyfitness-20261126193241", "namespace": "default"}
                    0  {"job_name": "thelounge-20261126195518", "namespace": "default"}
                    0  {"job_name": "thelounge-remote-20261126193330", "namespace": "default"}
                    0  {"job_name": "watchstate-remote-20261126194557", "namespace": "media"}

====================================================================================================
6. Rule health for everything this investigation shipped (retry, long timeout)
====================================================================================================
Traceback (most recent call last):
  File "/Users/jkchai/Developer/PUBLIC/chaijunkin-home-ops/docs/investigations/vpn-services-lan-outage-2026-11-21/scripts/039-speedtest-absent-check.py", line 108, in <module>
    found[r["name"]] = (g["namespace"], g["group"], r)
                        ~^^^^^^^^^^^^^
KeyError: 'namespace'
