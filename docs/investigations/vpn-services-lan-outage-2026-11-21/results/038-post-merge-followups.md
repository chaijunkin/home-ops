
====================================================================================================
1. The orphan volsync-system Namespace
====================================================================================================
     annotations:
       kustomize.toolkit.fluxcd.io/prune: disabled
     labels:
       kubernetes.io/metadata.name: volsync-system
       kustomize.toolkit.fluxcd.io/name: cluster-apps
       kustomize.toolkit.fluxcd.io/namespace: flux-system
     name: volsync-system
     finalizers:
     phase: Active

   objects still inside:
    configmap/kube-root-ca.crt   1     166d
serviceaccount/default   166d

   does anything still own/label objects here (Flux owner refs)?
    error: the server doesn't have a resource type "default"

====================================================================================================
2. Is Prometheus still scraping speedtest-exporter?
====================================================================================================
   targets mentioning speedtest: 1
     job=speedtest-exporter health=up lastError=-
       scrapeUrl=http://10.69.0.185:9798/metrics lastScrape=2026-11-26T19:27:55.483062097Z lastDuration=22.632570275 samples=None

   how many targets are unhealthy overall:
     0 unhealthy

   speedtest metric presence over the last 3h (60m scrape interval):
     absent(speedtest_download_bits_per_second)           -> 1  

====================================================================================================
3. Alerts that need a name attached
====================================================================================================
   KubeJobFailed:
     1  alertname=KubeJobFailed namespace=ai job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeJobFailed namespace=ai job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeJobFailed namespace=ai job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeJobFailed namespace=renovate job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     job names (24h):
   KubeHpaMaxedOut:
     1  alertname=KubeHpaMaxedOut namespace=downloads job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=downloads job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=media job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=media job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=home-automation job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=media job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=storage job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=downloads job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=downloads job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=media job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=downloads job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=downloads job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=downloads job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=storage job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=downloads job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=downloads job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=media job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=downloads job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=media job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=media job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=media job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     1  alertname=KubeHpaMaxedOut namespace=media job=kube-state-metrics instance=10.69.0.43:8080 severity=warning
     job names (24h):

====================================================================================================
4. Deployed rule health (what #2604/#2607/#2608 shipped + the deleted one)
====================================================================================================
Traceback (most recent call last):
  File "/Users/jkchai/Developer/PUBLIC/chaijunkin-home-ops/docs/investigations/vpn-services-lan-outage-2026-11-21/scripts/038-post-merge-followups.py", line 149, in <module>
    raise SystemExit(main())
                     ~~~~^^
  File "/Users/jkchai/Developer/PUBLIC/chaijunkin-home-ops/docs/investigations/vpn-services-lan-outage-2026-11-21/scripts/038-post-merge-followups.py", line 122, in main
    found[r["name"]] = (g["namespace"], g["group"], r)
                        ~^^^^^^^^^^^^^
KeyError: 'namespace'
