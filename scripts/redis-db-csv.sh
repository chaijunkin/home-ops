#!/usr/bin/env bash
set -euo pipefail

# Generate CSV of Redis database index allocations.
# CSV format: title,subtitle,args

OUT_CSV="docs/redis-db.csv"
SVC_MD="docs/redis-db.md"
TMP_JSON=$(mktemp)

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl not found in PATH" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq not found in PATH" >&2
  exit 1
fi

echo "Fetching HelmRelease and ConfigMap resources..."
kubectl get hr,cm -A -o json > "$TMP_JSON" 2>/dev/null || echo '{"items":[]}' > "$TMP_JSON"

echo "title,subtitle,args" > "$OUT_CSV"

echo "# Redis DB List" > "$SVC_MD"
echo "| Namespace | App | DB Index |" >> "$SVC_MD"
echo "| --- | --- | --- |" >> "$SVC_MD"

# Parse resources for redis://.../[0-9]+
jq -r '
  .items[] |
  (.metadata.namespace // "default") as $ns |
  (.metadata.name) as $name |
  (
    # Search within stringified spec/data for redis://
    [.. | strings | capture("redis://[^/]+:6379/(?<db>\\d+)")] | .[0].db // empty
  ) as $db |
  "\($ns)\t\($name)\t\($db)"
' "$TMP_JSON" | sort -n -k 3 -t $'\t' | while IFS=$'\t' read -r ns name db; do
  if [[ -n "$db" ]]; then
    printf '"%s","%s","%s"\n' "$name" "$ns | Redis DB" "DB $db" >> "$OUT_CSV"
    printf '| %s | %s | %s |\n' "$ns" "$name" "$db" >> "$SVC_MD"
  fi
done

rm -f "$TMP_JSON"

echo "Wrote $OUT_CSV"
echo "Wrote $SVC_MD"
