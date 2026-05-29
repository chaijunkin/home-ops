#!/usr/bin/env bash
set -euo pipefail

# Generate CSV of HTTPRoute hostnames and LoadBalancer services, their backend service and LB IP/port,
# update docs/cilium-ipam.md with lists, and generate docs/services-list.md.
# CSV format: title,subtitle,args
# where args is a compact JSON string with details.
# Requires: kubectl, jq

OUT_CSV="docs/httproutes.csv"
SVC_MD="docs/services-list.md"
TMP_JSON=$(mktemp)
SVC_JSON=$(mktemp)
RESV_TMP=$(mktemp)
MISSING_TMP=$(mktemp)
HTTPROUTE_BACKENDS=$(mktemp)

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl not found in PATH" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "jq not found in PATH" >&2
  exit 1
fi

echo "Fetching HTTPRoute and Service resources..."
kubectl get httproute -A -o json > "$TMP_JSON" 2>/dev/null || echo '{"items":[]}' > "$TMP_JSON"
kubectl get svc -A -o json > "$SVC_JSON" 2>/dev/null || echo '{"items":[]}' > "$SVC_JSON"

echo "title,subtitle,args" > "$OUT_CSV"

echo "# Services List" > "$SVC_MD"
echo "| Namespace | App | URL | Homepage Group |" >> "$SVC_MD"
echo "| --- | --- | --- | --- |" >> "$SVC_MD"

# Extract all backends used by HTTPRoutes (format: namespace/name)
jq -r '
  .items[] |
  (.metadata.namespace // "default") as $ns |
  (.spec.rules // [])[]?.backendRefs[]? |
  select(. != null) |
  ( .name // .backendRef?.name ) as $bname |
  "\($ns)/\($bname)"
' "$TMP_JSON" | sort -u > "$HTTPROUTE_BACKENDS"

# Produce lines with host,namespace,httproute,parent,backendName,backendPort,homepageEnabled,homepageGroup
jq -r '
  .items[] as $r |
  ($r.spec.hostnames // [])[] as $h |
  ($r.metadata.namespace // "default") as $ns |
  ($r.metadata.name) as $name |
  (($r.spec.parentRefs // [])[]?.name // "") as $parent |
  ($r.metadata.annotations["gethomepage.dev/enabled"] // "false") as $hp_enabled |
  ($r.metadata.annotations["gethomepage.dev/group"] // "None") as $hp_group |
  (
    ($r.spec.rules // [])[]?.backendRefs[]? // [] |
    select(. != null) |
    ( .name // .backendRef?.name // "" ) as $bname |
    ( .port // .backendRef?.port?.number // .backendRef?.port // null ) as $bport |
    "\($h)\t\($ns)\t\($name)\t\($parent)\t\($bname)\t\($bport)\t\($hp_enabled)\t\($hp_group)"
  )' "$TMP_JSON" | while IFS=$'\t' read -r host ns name parent backend backendPort hp_enabled hp_group; do
  # Normalize empty backend
  backend=${backend:-}
  backendPort=${backendPort:-}

  lb_ip=""
  svc_port=""
  if [[ -n "$backend" ]]; then
    # try to read service in same namespace from our dumped json
    svc_json=$(jq -c --arg ns "$ns" --arg n "$backend" '.items[] | select(.metadata.namespace == $ns and .metadata.name == $n)' "$SVC_JSON" || true)
    if [[ -n "$svc_json" ]]; then
      # check annotations for lbipam
      lb_ann=$(echo "$svc_json" | jq -r '.metadata.annotations["lbipam.cilium.io/ips"] // .metadata.annotations["io.cilium/lb-ipam-ips"] // empty')
      if [[ -n "$lb_ann" ]]; then
        lb_ip=$(echo "$lb_ann" | awk -F"," '{print $1}' | tr -d ' "')
      else
        lb_ip=$(echo "$svc_json" | jq -r '.status.loadBalancer.ingress[0].ip // .status.loadBalancer.ingress[0].hostname // empty')
      fi

      if [[ -n "$backendPort" && "$backendPort" != "null" ]]; then
        svc_port=$(echo "$svc_json" | jq -r --arg bp "$backendPort" '.spec.ports[] | select((.port|tostring)==$bp or (.name==$bp)) | .port' 2>/dev/null | head -n1 || true)
      fi
      if [[ -z "$svc_port" ]]; then
        svc_port=$(echo "$svc_json" | jq -r '.spec.ports[0].port // empty' 2>/dev/null || true)
      fi
    fi
  fi

  if [[ -n "$backend" ]]; then
    title="$backend"
  else
    title="$name"
  fi

  class="unknown"
  if [[ "$parent" == *external* ]]; then
    class="external"
  elif [[ "$parent" == *internal* ]]; then
    class="internal"
  fi

  if [[ -n "$parent" ]]; then
    if [[ "$class" != "unknown" && "$parent" == *"$class"* ]]; then
      subtitle="$ns | $parent"
    else
      subtitle="$ns | $class | $parent"
    fi
  else
    subtitle="$ns | $class"
  fi

  args_field="$host"

  printf '"%s","%s","%s"\n' "$title" "$subtitle" "$args_field" >> "$OUT_CSV"
  printf '| %s | %s | %s | %s |\n' "$ns" "$name" "$host" "$hp_group" >> "$SVC_MD"

  if [[ "$hp_enabled" != "true" ]]; then
    printf -- '- %s/%s (%s)\n' "$ns" "$name" "$host" >> "$MISSING_TMP"
  fi

  if [[ -n "$lb_ip" ]]; then
    printf -- '- %s - %s/%s (port: %s)\n' "$lb_ip" "$ns" "$backend" "${svc_port:-unknown}" >> "$RESV_TMP"
  fi
done

# Now process LoadBalancer services that are not referenced by an HTTPRoute
jq -r '
  .items[] |
  select(.spec.type == "LoadBalancer") |
  (.metadata.namespace // "default") as $ns |
  (.metadata.name) as $name |
  (.metadata.annotations["gethomepage.dev/enabled"] // "false") as $hp_enabled |
  (.metadata.annotations["gethomepage.dev/group"] // "None") as $hp_group |
  (.metadata.annotations["external-dns.alpha.kubernetes.io/hostname"] // "") as $hostname |
  (.spec.ports[0].port // "") as $port |
  "\($ns)\t\($name)\t\($hp_enabled)\t\($hp_group)\t\($hostname)\t\($port)"
' "$SVC_JSON" | while IFS=$'\t' read -r ns name hp_enabled hp_group hostname port; do
  # Check if this service is in HTTPROUTE_BACKENDS
  if grep -q "^${ns}/${name}$" "$HTTPROUTE_BACKENDS"; then
    continue
  fi

  host="$hostname"
  if [[ -z "$host" ]]; then
    # find lb ip
    svc_json=$(jq -c --arg ns "$ns" --arg n "$name" '.items[] | select(.metadata.namespace == $ns and .metadata.name == $n)' "$SVC_JSON")
    lb_ann=$(echo "$svc_json" | jq -r '.metadata.annotations["lbipam.cilium.io/ips"] // .metadata.annotations["io.cilium/lb-ipam-ips"] // empty')
    if [[ -n "$lb_ann" ]]; then
      lb_ip=$(echo "$lb_ann" | awk -F"," '{print $1}' | tr -d ' "')
    else
      lb_ip=$(echo "$svc_json" | jq -r '.status.loadBalancer.ingress[0].ip // .status.loadBalancer.ingress[0].hostname // empty')
    fi
    if [[ -n "$lb_ip" ]]; then
      host="$lb_ip:$port"
    else
      host="<unknown>"
    fi
  else
    # if lb ip is found, still write to RESV_TMP
    svc_json=$(jq -c --arg ns "$ns" --arg n "$name" '.items[] | select(.metadata.namespace == $ns and .metadata.name == $n)' "$SVC_JSON")
    lb_ann=$(echo "$svc_json" | jq -r '.metadata.annotations["lbipam.cilium.io/ips"] // .metadata.annotations["io.cilium/lb-ipam-ips"] // empty')
    if [[ -n "$lb_ann" ]]; then
      lb_ip=$(echo "$lb_ann" | awk -F"," '{print $1}' | tr -d ' "')
    else
      lb_ip=$(echo "$svc_json" | jq -r '.status.loadBalancer.ingress[0].ip // .status.loadBalancer.ingress[0].hostname // empty')
    fi
    if [[ -n "$lb_ip" ]]; then
      printf -- '- %s - %s/%s (port: %s)\n' "$lb_ip" "$ns" "$name" "${port:-unknown}" >> "$RESV_TMP"
    fi
  fi

  title="$name"
  subtitle="$ns | LoadBalancer"
  args_field="$host"

  printf '"%s","%s","%s"\n' "$title" "$subtitle" "$args_field" >> "$OUT_CSV"
  printf '| %s | %s | %s | %s |\n' "$ns" "$name" "$host" "$hp_group" >> "$SVC_MD"

  if [[ "$hp_enabled" != "true" ]]; then
    printf -- '- %s/%s (%s)\n' "$ns" "$name" "$host" >> "$MISSING_TMP"
  fi
done

echo "Wrote $OUT_CSV"
echo "Wrote $SVC_MD"

if [[ -s "$MISSING_TMP" ]]; then
  echo -e "\nWARNING: The following services are missing homepage annotations (gethomepage.dev/enabled: \"true\"):"
  cat "$MISSING_TMP" | sort | uniq
  echo -e "\nPlease update their HTTPRoute or HelmRelease values to include the required annotations."
fi

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
  sort "$EXT_MD" | uniq >> docs/cilium-ipam.md
else
  echo "_None found_" >> docs/cilium-ipam.md
fi

cat >> docs/cilium-ipam.md <<'DOCS'

#### Internal services
DOCS

if [[ -s "$INT_MD" ]]; then
  sort "$INT_MD" | uniq >> docs/cilium-ipam.md
else
  echo "_None found_" >> docs/cilium-ipam.md
fi

cat >> docs/cilium-ipam.md <<'DOCS'

#### Reserved IPs (excerpt)
```
DOCS

for rl in "${_reserved_lines[@]:-}"; do
  printf '%s\n' "$rl" >> docs/cilium-ipam.md
done

if [[ -s "$RESV_TMP" ]]; then
  printf '\n' >> docs/cilium-ipam.md
  sort -V -t' ' -k2 "$RESV_TMP" | uniq >> docs/cilium-ipam.md
fi

cat >> docs/cilium-ipam.md <<'DOCS'
```
DOCS

rm -f "$TMP_JSON" "$SVC_JSON" "$EXT_MD" "$INT_MD" "$RESV_TMP" "$MISSING_TMP" "$HTTPROUTE_BACKENDS"

echo "Updated docs/cilium-ipam.md"
