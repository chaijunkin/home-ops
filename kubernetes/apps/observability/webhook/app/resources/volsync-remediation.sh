#!/bin/sh
# Query Prometheus for VolSyncVolumeOutOfSync alerts
alerts=$(curl -s "http://prometheus-operated.observability.svc.cluster.local:9090/api/v1/alerts")

# Filter and iterate over alerts
echo "$alerts" | jq -r '.data.alerts[] | select(.labels.alertname == "VolSyncVolumeOutOfSync") | "\(.labels.obj_namespace) \(.labels.obj_name)"' |
while read -r namespace name; do
  if [ -n "$namespace" ] && [ -n "$name" ]; then
    echo "Triggering manual sync for $namespace/$name"
    kubectl patch replicationsource "$name" -n "$namespace" --type merge -p "{\"spec\":{\"trigger\":{\"manual\":\"$(date +%s)\"}}}"
    # Remove finalizers and delete the associated VolumeSnapshot
    kubectl patch volumesnapshot "volsync-$name-src" -n "$namespace" -p '{"metadata":{"finalizers":[]}}' --type merge || true
    kubectl delete volumesnapshot "volsync-$name-src" -n "$namespace" --ignore-not-found
  fi
done
