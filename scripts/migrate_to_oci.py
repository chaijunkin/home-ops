
import os
import re
import yaml

# List of HelmRepository files to be removed after migration
helm_repo_files_to_remove = set()

# Mapping from HelmRepository name to OCI URL
# This should be populated with the correct OCI URLs for your charts
oci_url_map = {
    "jetstack": "oci://ghcr.io/jetstack/charts",
    "cloudnative-pg": "oci://ghcr.io/cloudnative-pg/charts",
    "csi-driver-smb": "oci://ghcr.io/csi-driver-smb/csi-driver-smb",
    "external-secrets": "oci://ghcr.io/external-secrets/helm-charts",
    "intel": "oci://ghcr.io/intel/helm-charts",
    "metrics-server": "oci://ghcr.io/metrics-server/charts",
    "node-feature-discovery": "oci://ghcr.io/k8s-sig-node/charts",
    "stakater": "oci://ghcr.io/stakater/charts",
    "external-dns": "oci://ghcr.io/kubernetes-sigs/external-dns-charts",
    "ingress-nginx": "oci://ghcr.io/kubernetes/ingress-nginx",
    "angelnu": "oci://ghcr.io/angelnu/charts",
    "prometheus-community": "oci://ghcr.io/prometheus-community/charts",
    "grafana": "oci://ghcr.io/grafana/helm-charts",
    "openebs": "oci://ghcr.io/openebs/charts",
    "authentik-charts": "oci://ghcr.io/goauthentik/helm-charts",
    "democratic-csi-charts": "oci://ghcr.io/democratic-csi/charts",
    "piraeus": "oci://ghcr.io/piraeus-datastore/charts",
    "backube": "oci://ghcr.io/backube/charts",
}

def find_helmrelease_file(app_path):
    """Finds the helmrelease.yaml file in the application's directory."""
    for root, _, files in os.walk(app_path):
        for file in files:
            if file == "helmrelease.yaml":
                return os.path.join(root, file)
    return None

def migrate_helmrelease(file_path, oci_url, chart_name, release_name, namespace):
    """Migrates a single HelmRelease to use an OCIRepository."""
    with open(file_path, 'r') as f:
        content = f.read()
        docs = list(yaml.safe_load_all(content))

    helmrelease_doc = None
    for doc in docs:
        if doc and doc.get("kind") == "HelmRelease":
            helmrelease_doc = doc
            break

    if not helmrelease_doc:
        print(f"Could not find HelmRelease in {file_path}")
        return

    # Check if it's already migrated or uses chartRef
    if "chartRef" in helmrelease_doc["spec"]:
        print(f"Skipping {file_path}, already uses chartRef.")
        return

    # Create OCIRepository
    ocirepository = {
        "apiVersion": "source.toolkit.fluxcd.io/v1",
        "kind": "OCIRepository",
        "metadata": {
            "name": release_name,
            "namespace": namespace
        },
        "spec": {
            "interval": "5m",
            "url": oci_url,
            "ref": {
                "tag": helmrelease_doc["spec"]["chart"]["version"] # Assumes version is present
            }
        }
    }

    # Update HelmRelease
    helmrelease_doc["spec"]["chart"] = {
        "spec": {
            "chart": chart_name,
            "sourceRef": {
                "kind": "OCIRepository",
                "name": release_name,
                "namespace": namespace
            }
        }
    }

    # Combine and write back to file
    all_docs = [ocirepository] + docs
    with open(file_path, 'w') as f:
        yaml.dump_all(all_docs, f, default_flow_style=False, sort_keys=False)
    print(f"Migrated {file_path}")


def main():
    error_log = """
    FAILED kubernetes/flux/cluster::cert-manager::cert-manager/cert-manager - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-jetstack/cert-manager for HelmRelease cert-manager
    FAILED kubernetes/flux/cluster::cloudnative-pg::database/cloudnative-pg - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-cloudnative-pg/cloudnative-pg for HelmRelease cloudnative-pg
    FAILED kubernetes/flux/cluster::csi-driver-smb::kube-system/csi-driver-smb - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-csi-driver-smb/csi-driver-smb for HelmRelease csi-driver-smb
    FAILED kubernetes/flux/cluster::external-secrets::kube-system/external-secrets - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-external-secrets/external-secrets for HelmRelease external-secrets
    FAILED kubernetes/flux/cluster::intel-device-plugin::kube-system/intel-device-plugin-operator - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-intel/intel-device-plugins-operator for HelmRelease intel-device-plugin-operator
    FAILED kubernetes/flux/cluster::intel-device-plugin-gpu::kube-system/intel-device-plugin-gpu - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-intel/intel-device-plugins-gpu for HelmRelease intel-device-plugin-gpu
    FAILED kubernetes/flux/cluster::metrics-server::kube-system/metrics-server - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-metrics-server/metrics-server for HelmRelease metrics-server
    FAILED kubernetes/flux/cluster::node-feature-discovery::kube-system/node-feature-discovery - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-node-feature-discovery/node-feature-discovery for HelmRelease node-feature-discovery
    FAILED kubernetes/flux/cluster::reloader::kube-system/reloader - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-stakater/reloader for HelmRelease reloader
    FAILED kubernetes/flux/cluster::external-dns::network/external-dns - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-external-dns/external-dns for HelmRelease external-dns
    FAILED kubernetes/flux/cluster::ingress-nginx-external::network/ingress-nginx-external - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-ingress-nginx/ingress-nginx for HelmRelease ingress-nginx-external
    FAILED kubernetes/flux/cluster::ingress-nginx-internal::network/ingress-nginx-internal - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-ingress-nginx/ingress-nginx for HelmRelease ingress-nginx-internal
    FAILED kubernetes/flux/cluster::multus::network/multus - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-angelnu/multus for HelmRelease multus
    FAILED kubernetes/flux/cluster::blackbox-exporter::observability/blackbox-exporter - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-prometheus-community/prometheus-blackbox-exporter for HelmRelease blackbox-exporter
    FAILED kubernetes/flux/cluster::grafana::observability/grafana - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-grafana/grafana for HelmRelease grafana
    FAILED kubernetes/flux/cluster::kube-prometheus-stack::observability/kube-prometheus-stack - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-prometheus-community/kube-prometheus-stack for HelmRelease kube-prometheus-stack
    FAILED kubernetes/flux/cluster::loki::observability/loki - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-grafana/loki for HelmRelease loki
    FAILED kubernetes/flux/cluster::openebs::openebs-system/openebs - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-openebs/openebs for HelmRelease openebs
    FAILED kubernetes/flux/cluster::authentik::security/authentik - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-authentik-charts/authentik for HelmRelease authentik
    FAILED kubernetes/flux/cluster::local-hostpath::storage/local-hostpath - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-democratic-csi-charts/democratic-csi for HelmRelease local-hostpath
    FAILED kubernetes/flux/cluster::snapshot-controller::volsync-system/snapshot-controller - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-piraeus/snapshot-controller for HelmRelease snapshot-controller
    FAILED kubernetes/flux/cluster::volsync::volsync-system/volsync - flux_local.exceptions.HelmException: Unable to find HelmRepository for flux-system-backube/volsync for HelmRelease volsync
    """

    base_dir = "kubernetes/apps"

    for line in error_log.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # Parse the format: kubernetes/flux/cluster::app-name::namespace/release-name
        parts = line.split("::")
        if len(parts) < 3:
            continue

        # Extract namespace and release name from the third part
        app_path_part = parts[2]
        if "/" not in app_path_part:
            continue
        
        namespace, release_name = app_path_part.split("/", 1)

        # Extract repository and chart info from the error message
        match = re.search(r'flux-system-(.*?)/(.*?) for HelmRelease (.*)', line)
        if not match:
            continue

        repo_name, chart_name, _ = match.groups()

        if repo_name not in oci_url_map:
            print(f"Warning: No OCI URL mapping for repository '{repo_name}'. Skipping {release_name}.")
            continue

        app_path = os.path.join(base_dir, namespace, release_name)
        if not os.path.isdir(app_path):
            # Handle cases where app name and release name differ
            app_path = os.path.join(base_dir, namespace, release_name.split("-")[0])
            if not os.path.isdir(app_path):
                print(f"Warning: Could not find directory for {release_name} in {namespace}. Looked in {app_path}")
                continue

        hr_file = find_helmrelease_file(app_path)
        if not hr_file:
            print(f"Warning: Could not find helmrelease.yaml for {release_name} in {app_path}")
            continue

        oci_url = oci_url_map[repo_name]
        migrate_helmrelease(hr_file, oci_url, chart_name, release_name, namespace)

        # Mark the old HelmRepository file for deletion
        helm_repo_files_to_remove.add(f"kubernetes/flux/repositories/helm/{repo_name}.yaml")

    # Clean up old HelmRepository files
    for file_path in helm_repo_files_to_remove:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Removed old HelmRepository file: {file_path}")

if __name__ == "__main__":
    main()
