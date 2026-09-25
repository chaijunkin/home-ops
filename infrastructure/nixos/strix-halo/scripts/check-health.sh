#!/usr/bin/env bash
# Health check script for Strix Halo NixOS services

HOST="root@192.168.1.149"

echo "============================================="
echo "   Strix Halo Service Health Check           "
echo "============================================="
echo ""

echo ">>> Checking Systemd Services..."
ssh -o StrictHostKeyChecking=no $HOST "systemctl is-active podman-strix-halo-27b podman-nemotron-3.5 podman-gemma-4 podman-memini-embed podman-memini-rerank podman-whisper podman-comfyui" | awk '
BEGIN {
    split("strix-halo-27b nemotron-3.5 gemma-4 memini-embed memini-rerank whisper comfyui", services, " ")
    i = 1
}
{
    printf "%-25s : %s\n", services[i], $0
    i++
}
'
echo ""

echo ">>> Checking HTTP /health Endpoints..."
SERVICES=(
    "strix-halo-27b:8732"
    "nemotron-3.5:8733"
    "gemma-4:8734"
    "memini-embed:8735"
    "memini-rerank:8736"
    "whisper:8081"
)

for SERVICE in "${SERVICES[@]}"; do
    NAME="${SERVICE%%:*}"
    PORT="${SERVICE##*:}"
    
    # Send a quick curl request to the health endpoint (2 seconds timeout)
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 "http://192.168.1.149:${PORT}/health" || echo "failed")
    
    if [ "$STATUS" = "200" ]; then
        printf "%-25s : \033[32mOK (200)\033[0m on port %s\n" "$NAME" "$PORT"
    elif [[ "$STATUS" == *"failed"* ]] || [[ "$STATUS" == *"000"* ]]; then
        printf "%-25s : \033[31mUNREACHABLE\033[0m on port %s\n" "$NAME" "$PORT"
    else
        printf "%-25s : \033[33mHTTP %s\033[0m on port %s\n" "$NAME" "$STATUS" "$PORT"
    fi
done

echo ""
echo "============================================="
echo "   Container Status (podman ps)              "
echo "============================================="
ssh -o StrictHostKeyChecking=no $HOST "podman ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
