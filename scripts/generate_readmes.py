import os
import re
import glob

repo_apps_dir = "/Users/jkchai/Developer/PUBLIC/chaijunkin-home-ops/kubernetes/apps"

cloud_native_ns = [
    "actions-runner-system", "cert-manager", "external-secrets", "flux-system",
    "jobs", "kube-system", "network", "observability", "renovate", "security",
    "storage", "system-upgrade", "volsync-system"
]

# Static knowledge mapping for popular applications
APP_KNOWLEDGE = {
    "opencloud": {"url": "https://github.com/owncloud/core", "desc": "Personal cloud file storage and sharing."},
    "cert-manager": {"url": "https://github.com/cert-manager/cert-manager", "desc": "Automatically provision and manage TLS certificates in Kubernetes."},
    "external-secrets": {"url": "https://github.com/external-secrets/external-secrets", "desc": "Operator that reads information from external APIs and automatically injects the values into a Kubernetes Secret."},
    "jellyfin": {"url": "https://github.com/jellyfin/jellyfin", "desc": "The Free Software Media System."},
    "plex": {"url": "https://github.com/plexinc", "desc": "Client-server media player system."},
    "radarr": {"url": "https://github.com/Radarr/Radarr", "desc": "A fork of Sonarr to work with movies à la Couchpotato."},
    "sonarr": {"url": "https://github.com/Sonarr/Sonarr", "desc": "Smart PVR for newsgroup and bittorrent users."},
    "home-assistant": {"url": "https://github.com/home-assistant/core", "desc": "Open source home automation that puts local control and privacy first."},
    "flux-system": {"url": "https://github.com/fluxcd/flux2", "desc": "Open and extensible continuous delivery solution for Kubernetes."},
    "kube-prometheus-stack": {"url": "https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack", "desc": "Collection of Kubernetes manifests, Grafana dashboards, and Prometheus rules."},
    "cilium": {"url": "https://github.com/cilium/cilium", "desc": "eBPF-based Networking, Security, and Observability."},
    "authentik": {"url": "https://github.com/goauthentik/authentik", "desc": "The authentication glue you need."},
    "bitwarden": {"url": "https://github.com/bitwarden/server", "desc": "Open source password management solutions."},
    "volsync": {"url": "https://github.com/backube/volsync", "desc": "Asynchronous data replication for Kubernetes volumes."},
    "renovate": {"url": "https://github.com/renovatebot/renovate", "desc": "Universal dependency update tool that fits into your workflows."},
    "cloudnative-pg": {"url": "https://github.com/cloudnative-pg/cloudnative-pg", "desc": "PostgreSQL Operator for Kubernetes."},
    "qbittorrent": {"url": "https://github.com/qbittorrent/qBittorrent", "desc": "Free and reliable P2P BitTorrent client."},
    "frigate": {"url": "https://github.com/blakeblackshear/frigate", "desc": "NVR with realtime local object detection for IP cameras."},
    "minecraft": {"url": "https://github.com/itzg/docker-minecraft-server", "desc": "Minecraft Server."},
    "actions-runner-controller": {"url": "https://github.com/actions/actions-runner-controller", "desc": "Kubernetes controller for GitHub Actions self-hosted runners."},
    "cloudflare-tunnel": {"url": "https://github.com/cloudflare/cloudflared", "desc": "Cloudflare Tunnel client (formerly Argo Tunnel)."},
    "external-dns": {"url": "https://github.com/kubernetes-sigs/external-dns", "desc": "Configure external DNS servers (AWS Route53, Google CloudDNS and others) for Kubernetes Ingresses and Services."},
    "grafana-operator": {"url": "https://github.com/grafana/grafana-operator", "desc": "A Kubernetes operator for Grafana."},
    "kyverno": {"url": "https://github.com/kyverno/kyverno", "desc": "Kubernetes Native Policy Management."},
    "trivy-operator": {"url": "https://github.com/aquasecurity/trivy-operator", "desc": "Kubernetes-native security scanner."},
    "openebs": {"url": "https://github.com/openebs/openebs", "desc": "Kubernetes storage natively integrated with the Kubernetes orchestrator."},
    "syncthing": {"url": "https://github.com/syncthing/syncthing", "desc": "Open Source Continuous File Synchronization."},
    "paperless": {"url": "https://github.com/paperless-ngx/paperless-ngx", "desc": "A supercharged version of paperless: scan, index and archive all your physical documents."},
}

def analyze_app(app_path):
    manifest_source = "Unknown"
    yaml_files = glob.glob(os.path.join(app_path, "**/*.yaml"), recursive=True)
    
    for yf in yaml_files:
        with open(yf, 'r', encoding='utf-8') as f:
            content = f.read()
            url_match = re.search(r'url:\s*(https?://[^\s]+)', content)
            if url_match:
                manifest_source = url_match.group(1)
                break
            chart_match = re.search(r'repository:\s*(https?://[^\s]+)', content)
            if chart_match:
                manifest_source = chart_match.group(1)
                break
    return manifest_source

def generate_readme(app_name, namespace, app_path):
    knowledge = APP_KNOWLEDGE.get(app_name.lower(), {
        "url": f"https://github.com/search?q={app_name}", 
        "desc": "To be filled."
    })
    
    manifest_source = analyze_app(app_path)
    
    category_folder = "cloud-native" if namespace in cloud_native_ns else "application"
    prr_url = f"https://wiki.cloudjur.com/pages/tech/cloudjur/{category_folder}/{app_name.title()}"
    
    return f"""# {app_name.title()}

**Description:** {knowledge['desc']}
**Category:** {namespace}

---

## Resources
- **Project Repository:** [{app_name.title()} Source Code]({knowledge['url']})
- **Helm/Manifest Source:** `{manifest_source}`

---

## Related Links
- [Documentation]() <!-- Add link to upstream docs -->
- [Application PRR Document]({prr_url})

## Notes
- *Add operational notes, gotchas, or specific configurations here.*
"""

for ns in os.listdir(repo_apps_dir):
    ns_path = os.path.join(repo_apps_dir, ns)
    if not os.path.isdir(ns_path): continue
    
    for app in os.listdir(ns_path):
        app_path = os.path.join(ns_path, app)
        if not os.path.isdir(app_path): continue
        
        target_file = os.path.join(app_path, "README.md")
        new_content = generate_readme(app, ns, app_path)
            
        with open(target_file, "w", encoding='utf-8') as f:
            f.write(new_content)

print("README.md generation completed.")
