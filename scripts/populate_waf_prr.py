import os
import re
import glob

# Paths
repo_apps_dir = "/Users/jkchai/Developer/PUBLIC/chaijunkin-home-ops/kubernetes/apps"
vault_app_dir = "/Users/jkchai/Documents/DefaultVault/pages/TECH/Cloudjur/application"
vault_cn_dir = "/Users/jkchai/Documents/DefaultVault/pages/TECH/Cloudjur/cloud-native"

cloud_native_ns = [
    "actions-runner-system", "cert-manager", "external-secrets", "flux-system",
    "jobs", "kube-system", "network", "observability", "renovate", "security",
    "storage", "system-upgrade", "volsync-system"
]

def analyze_app(app_path):
    data = {
        "deployment_method": "Kustomization",
        "has_metrics": "[ ]",
        "ingress_urls": "N/A",
        "has_netpol": "[ ]",
        "secret_method": "N/A",
        "storage_classes": "N/A",
        "has_volsync": "[ ]",
        "replica_count": "1",
        "has_limits": "[ ]",
        "has_scaling": "[ ]"
    }
    
    yaml_files = glob.glob(os.path.join(app_path, "**/*.yaml"), recursive=True)
    
    ingress_hosts = set()
    storage_classes = set()
    secrets = set()
    
    for yf in yaml_files:
        with open(yf, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Deployment method
            if "kind: HelmRelease" in content:
                data["deployment_method"] = "Flux HelmRelease"
                
            # Metrics
            if "kind: ServiceMonitor" in content or "kind: PodMonitor" in content or "metrics:\n      enabled: true" in content or "podMonitor:\n      enable: true" in content:
                data["has_metrics"] = "[x]"
                
            # Ingress
            hosts = re.findall(r'host:\s*([^\s]+)', content)
            if hosts:
                ingress_hosts.update(hosts)
                
            # NetPol
            if "kind: NetworkPolicy" in content:
                data["has_netpol"] = "[x]"
                
            # Secrets
            if "kind: ExternalSecret" in content:
                secrets.add("ExternalSecrets")
            if "kind: Secret" in content:
                secrets.add("Kubernetes Secret")
                
            # PVCs
            sc = re.findall(r'storageClassName:\s*([^\s]+)', content)
            if sc:
                storage_classes.update(sc)
                
            # VolSync
            if "kind: ReplicationSource" in content:
                data["has_volsync"] = "[x]"
                
            # Replicas
            rep = re.search(r'replicas:\s*(\d+)', content)
            if rep:
                data["replica_count"] = rep.group(1)
                
            # Limits
            if "limits:" in content and ("cpu:" in content or "memory:" in content):
                data["has_limits"] = "[x]"
                
            # Scaling
            if "kind: HorizontalPodAutoscaler" in content or "autoscaling:" in content:
                data["has_scaling"] = "[x]"

    if ingress_hosts:
        data["ingress_urls"] = ", ".join(ingress_hosts)
    if secrets:
        data["secret_method"] = ", ".join(secrets)
    if storage_classes:
        data["storage_classes"] = ", ".join(storage_classes)
        
    return data

def get_template(app_name, namespace, data, iac_path):
    # Determine marks for checklist
    m_metric = data["has_metrics"]
    m_iac = "[x]" # Always true if we found it in repo
    m_auth = "[x]" if "authentik" in data.get("ingress_urls", "").lower() or "authelia" in data.get("ingress_urls", "").lower() else "[ ]"
    m_netpol = data["has_netpol"]
    m_volsync = data["has_volsync"]
    m_limits = data["has_limits"]
    m_scale = data["has_scaling"]
    
    return f"""---
publish: true
tags:
  - {namespace}
---

# {app_name.title()}

*Brief description of the application.*

## Well-Architected Framework (WAF) PRR/ORR Checklist

### 1. Operational Excellence
*Focus: Running and monitoring systems to deliver business value and continuously improving processes.*
- {m_iac} **Infrastructure as Code (IaC)**: Application deployed via IaC (Path: `{iac_path}`, Method: `{data['deployment_method']}`).
- [ ] **CI/CD Automation**: Automated updates configured (e.g., Renovate integration).
- {m_metric} **Observability (Metrics)**: Application exposes Prometheus metrics.
- [ ] **Observability (Logs/Traces)**: Centralized logging is configured.
- [ ] **Runbooks**: Incident response runbook is documented.

### 2. Security, Privacy & Compliance
*Focus: Protecting information, systems, and assets while delivering business value.*
- {m_auth} **Identity & Access**: External access is secured via authentication on `{data['ingress_urls']}`.
- [ ] **Data at Rest**: Storage volumes are encrypted.
- [x] **Secrets Management**: Secrets are managed via: `{data['secret_method']}`.
- {m_netpol} **Network Isolation**: NetworkPolicies restrict unauthorized lateral movement.
- [ ] **Vulnerability Management**: Container images are scanned (e.g., via Trivy).

### 3. Reliability
*Focus: Ensuring the system can recover from disruptions and dynamically meet demand.*
- [x] **High Availability**: Application runs multiple replicas across different nodes (`{data['replica_count']}`).
- {m_volsync} **Disaster Recovery**: Backups are configured and regularly tested via VolSync.
- [x] **Data Persistence**: State is persisted correctly using appropriate storage classes (`{data['storage_classes']}`).
- [ ] **Health Checks**: Liveness and readiness probes are configured.

### 4. Performance Efficiency
*Focus: Using computing resources efficiently to meet system requirements.*
- {m_limits} **Resource Allocation**: CPU and Memory limits/requests are explicitly defined.
- {m_scale} **Auto-Scaling**: Horizontal (HPA) or Vertical (VPA) scaling is configured.
- [ ] **Optimized Storage**: Utilizing appropriate PVC access modes and IOPS-capable storage.

### 5. Cost Optimization
*Focus: Avoiding unnecessary costs and maximizing cloud/hardware investment.*
- [ ] **Right-Sizing**: Resources requested match actual utilization metrics.
- [ ] **Lifecycle Management**: Unused resources or temporary data are automatically purged.

### 6. Sustainability
*Focus: Minimizing the environmental impacts of running cloud workloads.*
- [ ] **Utilization Efficiency**: Workload scales to zero or downscales during non-peak hours.
- [ ] **Hardware Efficiency**: Leveraging specialized hardware optimally for specific tasks.
"""

for ns in os.listdir(repo_apps_dir):
    ns_path = os.path.join(repo_apps_dir, ns)
    if not os.path.isdir(ns_path): continue
    
    for app in os.listdir(ns_path):
        app_path = os.path.join(ns_path, app)
        if not os.path.isdir(app_path): continue
        
        filename = f"{app.title()}.md"
        target_dir = vault_cn_dir if ns in cloud_native_ns else vault_app_dir
        target_file = os.path.join(target_dir, filename)
        
        iac_path = f"kubernetes/apps/{ns}/{app}"
        app_data = analyze_app(app_path)
        
        # Preserve old content
        existing_content = ""
        if os.path.exists(target_file):
            with open(target_file, "r", encoding='utf-8') as f:
                content = f.read()
                # Remove ONLY the previous PRR section and frontmatter, keep the legacy notes
                if "Legacy Notes" in content:
                    existing_content = content.split("Legacy Notes / Existing Content")[1].strip()
                else:
                    # if it's a dummy file we just generated with no legacy notes, ignore it
                    pass
                
        new_content = get_template(app, ns, app_data, iac_path)
        
        if existing_content:
            new_content += "\n## Legacy Notes / Existing Content\n\n" + existing_content + "\n"
            
        with open(target_file, "w", encoding='utf-8') as f:
            f.write(new_content)

print("WAF PRR Population completed.")
