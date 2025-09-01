#!/usr/bin/env bash
set -euo pipefail

# Generate CSV of HTTPRoute hostnames, their backend service and LB IP/port, and
# update docs/cilium-ipam.md with lists. CSV format: title,subtitle,args
# where args is a compact JSON string with details.
# Requires: kubectl, jq

OUT_CSV="docs/httproutes.csv"
TMP_JSON=$(mktemp)
RESV_TMP=$(mktemp)

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl not found in PATH" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq not found in PATH" >&2
  exit 1
fi

echo "Fetching HTTPRoute resources..."
kubectl get httproute -A -o json > "$TMP_JSON"

echo "title,subtitle,args" > "$OUT_CSV"

# Produce lines with host,namespace,httproute,parent,backendName,backendPort
jq -r '
  .items[] as $r |
  ($r.spec.hostnames // [])[] as $h |
  ($r.metadata.namespace // "default") as $ns |
  ($r.metadata.name) as $name |
  (($r.spec.parentRefs // [])[]?.name // "") as $parent |
  (
    ($r.spec.rules // [])[]?.backendRefs[]? // [] |
    select(. != null) |
    ( .name // .backendRef?.name // "" ) as $bname |
    ( .port // .backendRef?.port?.number // .backendRef?.port // null ) as $bport |
    "\($h)\t\($ns)\t\($name)\t\($parent)\t\($bname)\t\($bport)"
  )' "$TMP_JSON" | while IFS=$'\t' read -r host ns name parent backend backendPort; do
  # Normalize empty backend
  backend=${backend:-}
  backendPort=${backendPort:-}

  lb_ip=""
  svc_port=""
  if [[ -n "$backend" ]]; then
    # try to read service in same namespace
    svc_json=$(kubectl get svc -n "$ns" "$backend" -o json 2>/dev/null || true)
    if [[ -n "$svc_json" ]]; then
      # check annotations for lbipam
      lb_ann=$(echo "$svc_json" | jq -r '.metadata.annotations["lbipam.cilium.io/ips"] // .metadata.annotations["io.cilium/lb-ipam-ips"] // empty')
      if [[ -n "$lb_ann" ]]; then
        # take first IP from comma-separated list
        lb_ip=$(echo "$lb_ann" | awk -F"," '{print $1}' | tr -d ' "')
      else
        # fallback to status.loadBalancer.ingress[].ip
        lb_ip=$(echo "$svc_json" | jq -r '.status.loadBalancer.ingress[0].ip // .status.loadBalancer.ingress[0].hostname // empty')
      fi

      # determine service port
      if [[ -n "$backendPort" && "$backendPort" != "null" ]]; then
        # find matching port entry
        svc_port=$(echo "$svc_json" | jq -r --arg bp "$backendPort" '.spec.ports[] | select((.port|tostring)==$bp or (.name==$bp)) | .port' 2>/dev/null | head -n1 || true)
      fi
      if [[ -z "$svc_port" ]]; then
        svc_port=$(echo "$svc_json" | jq -r '.spec.ports[0].port // empty' 2>/dev/null || true)
      fi
    fi
  fi

  # Build fields per requested format
  # title: App name (use backend service name if available, else httproute name)
  if [[ -n "$backend" ]]; then
    title="$backend"
  else
    title="$name"
  fi

  # class detection from parent
  class="unknown"
  if [[ "$parent" == *external* ]]; then
    class="external"
  elif [[ "$parent" == *internal* ]]; then
    class="internal"
  fi

  # Build subtitle, avoid duplicating the class if parent already mentions it
  if [[ -n "$parent" ]]; then
    if [[ "$class" != "unknown" && "$parent" == *"$class"* ]]; then
      subtitle="$ns | $parent"
    else
      subtitle="$ns | $class | $parent"
    fi
  else
    subtitle="$ns | $class"
  fi

  # args should be just the hostname
  args_field="$host"

  # CSV-quote fields
  printf '"%s","%s","%s"\n' "$title" "$subtitle" "$args_field" >> "$OUT_CSV"

  # If we found a LB ip, mark service as reserved (append to temp)
  if [[ -n "$lb_ip" ]]; then
    # store plain IP (no backticks/escaping) for later safe insertion
  printf -- '- %s - %s/%s (port: %s)\n' "$lb_ip" "$ns" "$backend" "${svc_port:-unknown}" >> "$RESV_TMP"
  fi
done

echo "Wrote $OUT_CSV"

# Also append lists to docs/cilium-ipam.md (external/internal) based on parent refs
EXT_MD=$(mktemp)
INT_MD=$(mktemp)

jq -r '.items[] as $r | ($r.spec.hostnames // [])[] as $h | ($r.metadata.namespace // "default") as $ns | ($r.metadata.name) as $name | (($r.spec.parentRefs // [])[]?.name // "") as $parent | "\($h)\t\($ns)\t\($name)\t\($parent)"' "$TMP_JSON" | \
while IFS=$'\t' read -r host ns name parent; do
  if [[ "$parent" == *external* ]]; then
  printf -- '- `%s` - %s/%s (parent: %s)\n' "$host" "$ns" "$name" "$parent" >> "$EXT_MD"
  elif [[ "$parent" == *internal* ]]; then
  printf -- '- `%s` - %s/%s (parent: %s)\n' "$host" "$ns" "$name" "$parent" >> "$INT_MD"
  fi
done

# Read reserved excerpt lines safely into an array (if present)
mapfile -t _reserved_lines < <(awk '/### Reserved\/Allocated IPs/{flag=1;next} /^$/{if(flag) exit} flag{print}' docs/cilium-ipam.md 2>/dev/null || true)

cat > docs/cilium-ipam.md <<'DOCS'
# Cilium Load Balancer IPAM

## IP Address Allocation

### Ranges
- ** httproute Internal**: `10.10.30.25/27`
- **httproute External**: `10.10.30.26/27`
- **k8s-Gateway**: `10.10.30.27/27`

### HTTPRoute Services (auto-generated)

#### External services
DOCS

if [[ -s "$EXT_MD" ]]; then
  cat "$EXT_MD" >> docs/cilium-ipam.md
else
  echo "_None found_" >> docs/cilium-ipam.md
fi

cat >> docs/cilium-ipam.md <<'DOCS'

#### Internal services
DOCS

if [[ -s "$INT_MD" ]]; then
  cat "$INT_MD" >> docs/cilium-ipam.md
else
  echo "_None found_" >> docs/cilium-ipam.md
fi

cat >> docs/cilium-ipam.md <<'DOCS'

#### Reserved IPs (excerpt)
```
DOCS

for rl in "${_reserved_lines[@]:-}"; do
  printf '%s
' "$rl" >> docs/cilium-ipam.md
done

if [[ -s "$RESV_TMP" ]]; then
  printf '%s
' "" >> docs/cilium-ipam.md
  cat "$RESV_TMP" >> docs/cilium-ipam.md
fi

cat >> docs/cilium-ipam.md <<'DOCS'
```
DOCS

rm -f "$TMP_JSON" "$EXT_MD" "$INT_MD"
rm -f "$RESV_TMP"

echo "Updated docs/cilium-ipam.md"
