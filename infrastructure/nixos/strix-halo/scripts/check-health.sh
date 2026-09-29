#!/usr/bin/env bash
# Health check script for Strix Halo NixOS services

HOST="root@192.168.1.149"

echo "============================================="
echo "   Strix Halo Service Health Check           "
echo "============================================="
echo ""

echo ">>> Checking Systemd Services..."
for SERVICE in qwen38-flash-next comfyui memini-embeddings memini-reranker drm-exporter; do
    STATUS=$(ssh -o BatchMode=yes "$HOST" "systemctl is-active podman-${SERVICE}.service" 2>/dev/null || echo "inactive")
    printf "%-25s : %s\n" "$SERVICE" "$STATUS"
done
echo ""

echo ">>> Checking HTTP Endpoints..."
SERVICES=(
    "qwen38-flash-next:8732/v1/models"
    "comfyui:8188/"
    "memini-embeddings:8743/health"
    "memini-reranker:8744/health"
)

for SERVICE in "${SERVICES[@]}"; do
    NAME="${SERVICE%%:*}"
    ENDPOINT="${SERVICE#*:}"
    
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 "http://192.168.1.149:${ENDPOINT}" || echo "failed")

    if [ "$STATUS" = "200" ]; then
        printf "%-25s : \033[32mOK (200)\033[0m at %s\n" "$NAME" "$ENDPOINT"
    elif [[ "$STATUS" == *"failed"* ]] || [[ "$STATUS" == *"000"* ]]; then
        printf "%-25s : \033[31mUNREACHABLE\033[0m at %s\n" "$NAME" "$ENDPOINT"
    else
        printf "%-25s : \033[33mHTTP %s\033[0m at %s\n" "$NAME" "$STATUS" "$ENDPOINT"
    fi
done

echo ""
echo "============================================="
echo "   Container Status (podman ps)              "
echo "============================================="
ssh -o BatchMode=yes "$HOST" "podman ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
