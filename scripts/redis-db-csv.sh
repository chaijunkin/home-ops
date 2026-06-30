#!/usr/bin/env bash
set -euo pipefail

# Generate CSV of Redis database index allocations by searching local files.
# CSV format: title,subtitle,args

OUT_CSV="docs/redis-db.csv"
SVC_MD="docs/redis-db.md"

mkdir -p docs

echo "title,subtitle,args" > "$OUT_CSV"

echo "# Redis DB List" > "$SVC_MD"
echo "| Namespace | App | DB Index |" >> "$SVC_MD"
echo "| --- | --- | --- |" >> "$SVC_MD"

# Search for redis:// URLs in kubernetes/apps directory
grep -r -E -o "redis://[^/]+:6379/[0-9]+" kubernetes/apps | while IFS=: read -r file url; do
    # Path format is typically kubernetes/apps/<namespace>/<app>/...
    IFS='/' read -r _ _ ns app _ <<< "$file"
    
    # Extract db index from the url
    db="${url##*/}"
    
    echo -e "${ns}\t${app}\t${db}"
done | sort -u | sort -n -k 3 -t $'\t' | while IFS=$'\t' read -r ns app db; do
    printf '"%s","%s","%s"\n' "$app" "$ns | Redis DB" "DB $db" >> "$OUT_CSV"
    printf '| %s | %s | %s |\n' "$ns" "$app" "$db" >> "$SVC_MD"
done

echo "Wrote $OUT_CSV"
echo "Wrote $SVC_MD"
