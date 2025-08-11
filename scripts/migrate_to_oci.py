
import os
import re
import yaml

# List of HelmRepository files to be removed after migration
helm_repo_files_to_remove = set()

# Mapping from HelmRepository name to OCI base URL (without specific chart name)
# The chart name will be appended dynamically based on the actual chart being used
oci_base_url_map = {
    "jetstack": "oci://quay.io/jetstack/charts",
    "cloudnative-pg": "oci://ghcr.io/cloudnative-pg/charts",
    "csi-driver-smb": "oci://ghcr.io/kubernetes-csi/csi-driver-smb",
    "external-secrets": "oci://ghcr.io/external-secrets/charts",
    "intel": "oci://ghcr.io/intel/intel-device-plugins",
    "metrics-server": "oci://ghcr.io/kubernetes-sigs/metrics-server",
    "kubernetes-sigs-nfd": "oci://ghcr.io/kubernetes-sigs/node-feature-discovery-charts",
    "node-feature-discovery": "oci://ghcr.io/kubernetes-sigs/node-feature-discovery-charts",
    "stakater": "oci://ghcr.io/stakater/charts",
    "external-dns": "oci://ghcr.io/home-operations/charts-mirror",
    "ingress-nginx": "oci://ghcr.io/kubernetes/ingress-nginx",
    "angelnu": "oci://ghcr.io/angelnu/charts",
    "prometheus-community": "oci://ghcr.io/prometheus-community/charts",
    "grafana": "oci://ghcr.io/grafana/helm-charts",
    "openebs": "oci://ghcr.io/openebs/charts",
    "authentik-charts": "oci://ghcr.io/goauthentik/helm-charts",
    "democratic-csi-charts": "oci://ghcr.io/democratic-csi/charts",
    "piraeus": "oci://ghcr.io/piraeusdatastore/charts",
    "backube": "oci://ghcr.io/backube/volsync",
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
    from ruamel.yaml import YAML
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # Prevent line wrapping

    try:
        # Read the file and parse with ruamel.yaml to preserve formatting
        with open(file_path, 'r') as f:
            docs = list(yaml.load_all(f))
    except Exception as e:
        print(f"Warning: Could not parse YAML in {file_path}: {e}")
        return

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

    # Extract version from the chart spec, with fallback to latest
    chart_version = "latest"
    try:
        chart_version = helmrelease_doc["spec"]["chart"]["spec"]["version"]
    except KeyError:
        try:
            chart_version = helmrelease_doc["spec"]["chart"]["version"]
        except KeyError:
            print(f"Warning: No version found in {file_path}, using 'latest'")

    # Create OCIRepository
    ocirepository = {
        "apiVersion": "source.toolkit.fluxcd.io/v1",
        "kind": "OCIRepository",
        "metadata": {
            "name": release_name
        },
        "spec": {
            "interval": "5m",
            "layerSelector": {
                "mediaType": "application/vnd.cncf.helm.chart.content.v1.tar+gzip",
                "operation": "copy"
            },
            "url": oci_url,
            "ref": {
                "tag": chart_version
            }
        }
    }

    # Update HelmRelease to use chartRef instead of chart.spec
    helmrelease_doc["spec"]["chartRef"] = {
        "kind": "OCIRepository",
        "name": release_name
    }
    
    # Remove old chart spec if it exists
    if "chart" in helmrelease_doc["spec"]:
        del helmrelease_doc["spec"]["chart"]

    # Combine and write back to file
    all_docs = [ocirepository] + docs
    with open(file_path, 'w') as f:
        yaml.dump_all(all_docs, f)
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

        # Extract namespace and release name from the third part (before any " - ")
        app_path_part = parts[2].split(" - ")[0]  # Remove error message part
        if "/" not in app_path_part:
            continue
        
        namespace, release_name = app_path_part.split("/", 1)

        # Extract repository and chart info from the error message
        match = re.search(r'flux-system-(.*?)/(.*?) for HelmRelease (.*)', line)
        if not match:
            continue

        repo_name, chart_name, _ = match.groups()

        if repo_name not in oci_base_url_map:
            print(f"Warning: No OCI URL mapping for repository '{repo_name}'. Skipping {release_name}.")
            continue

        app_path = os.path.join(base_dir, namespace, release_name)
        if not os.path.isdir(app_path):
            # Try alternative paths for apps with different directory structures
            alternatives = [
                os.path.join(base_dir, release_name),
                os.path.join(base_dir, namespace, release_name.split('-')[0])
            ]
            found = False
            for alt_path in alternatives:
                if os.path.isdir(alt_path):
                    app_path = alt_path
                    found = True
                    break
            
            if not found:
                tried_paths = [os.path.join(base_dir, namespace, release_name)] + alternatives
                print(f"Warning: Could not find directory for {release_name} in {namespace}. Tried paths: {tried_paths}")
                continue

        hr_file = find_helmrelease_file(app_path)
        if not hr_file:
            print(f"Warning: Could not find helmrelease.yaml for {release_name} in {app_path}")
            continue

        # Construct the full OCI URL with chart name
        base_url = oci_base_url_map[repo_name]
        oci_url = f"{base_url}/{chart_name}"
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
