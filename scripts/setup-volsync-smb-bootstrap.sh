#!/bin/bash

# Script to create volsync SMB repository bootstrap components for application namespaces
# This script creates a bootstrap folder in each application namespace and sets up
# the volsync-smb-repository PVC with dependency on SMB CSI driver

set -euo pipefail

# Define the base directory
BASE_DIR="kubernetes/apps"

# Define application namespaces (excluding system namespaces)
APP_NAMESPACES=(
    "default"
    "downloads"
    "media"
    "home-automation"
    "security"
    "observability"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

create_bootstrap_structure() {
    local namespace=$1
    local bootstrap_dir="${BASE_DIR}/${namespace}/_bootstrap"

    log_info "Creating bootstrap structure for namespace: ${namespace}"

    # Create bootstrap directory
    mkdir -p "${bootstrap_dir}/app"

    # Create kustomization.yaml for the bootstrap component
    cat > "${bootstrap_dir}/app/kustomization.yaml" << 'EOF'
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
components:
  - ../../../../components/volsync-smb-repository
EOF

    # Create the Flux Kustomization resource to deploy the bootstrap
    cat > "${bootstrap_dir}/ks.yaml" << EOF
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: &app volsync-smb-repository-${namespace}
  namespace: flux-system
spec:
  targetNamespace: ${namespace}
  commonMetadata:
    labels:
      app.kubernetes.io/name: *app
  dependsOn:
    - name: csi-driver-smb
      namespace: flux-system
  path: ./kubernetes/apps/${namespace}/_bootstrap/app
  prune: true
  sourceRef:
    kind: GitRepository
    name: flux-system
    namespace: flux-system
  wait: false
  interval: 1d
  retryInterval: 1m
  timeout: 5m
EOF

    log_info "✓ Created bootstrap structure for ${namespace}"
}

update_namespace_kustomization() {
    local namespace=$1
    local kustomization_file="${BASE_DIR}/${namespace}/kustomization.yaml"

    log_info "Updating kustomization.yaml for namespace: ${namespace}"

    # Check if kustomization.yaml exists
    if [[ ! -f "${kustomization_file}" ]]; then
        log_warn "Creating new kustomization.yaml for ${namespace}"
        cat > "${kustomization_file}" << EOF
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:


  - ./bootstrap/ks.yaml
EOF
    else
        # Check if bootstrap/ks.yaml is already in the resources
        if ! grep -q "bootstrap/ks.yaml" "${kustomization_file}"; then
            log_info "Adding bootstrap/ks.yaml to existing kustomization.yaml"
            # Create a backup
            cp "${kustomization_file}" "${kustomization_file}.backup"

            # Use awk to add the bootstrap line after the resources: line
            awk '
            /^resources:/ {
                print $0
                print "  - ./bootstrap/ks.yaml"
                next
            }
            { print }
            ' "${kustomization_file}.backup" > "${kustomization_file}"

            # Remove backup
            rm "${kustomization_file}.backup"
        else
            log_info "bootstrap/ks.yaml already exists in kustomization.yaml"
        fi
    fi

    log_info "✓ Updated kustomization.yaml for ${namespace}"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if we're in the correct directory
    if [[ ! -d "kubernetes/apps" ]]; then
        log_error "Please run this script from the root of your home-ops repository"
        return 1
    fi

    # Check if the volsync-smb-repository component exists
    if [[ ! -d "kubernetes/components/volsync-smb-repository" ]]; then
        log_error "volsync-smb-repository component not found at kubernetes/components/volsync-smb-repository"
        log_error "Please ensure the component exists before running this script"
        return 1
    fi

    # Check if SMB storage class exists
    if [[ ! -f "kubernetes/apps/kube-system/csi-driver-smb/app/smb-volsync-storageclass.yaml" ]]; then
        log_error "SMB volsync storage class not found"
        log_error "Please ensure smb-volsync-storageclass.yaml exists in kubernetes/apps/kube-system/csi-driver-smb/app/"
        return 1
    fi

    log_info "✓ All prerequisites met"
    return 0
}

show_summary() {
    log_info ""
    log_info "==============================================="
    log_info "           SETUP SUMMARY"
    log_info "==============================================="
    log_info ""
    log_info "Created bootstrap structures for the following namespaces:"
    for namespace in "${APP_NAMESPACES[@]}"; do
        if [[ -d "${BASE_DIR}/${namespace}/bootstrap" ]]; then
            log_info "  ✓ ${namespace}"
        fi
    done
    log_info ""
    log_info "Files created:"
    log_info "  • kubernetes/components/volsync-smb-repository/"
    log_info "    ├── kustomization.yaml"
    log_info "    └── pvc.yaml"
    log_info ""
    for namespace in "${APP_NAMESPACES[@]}"; do
        if [[ -d "${BASE_DIR}/${namespace}/bootstrap" ]]; then
            log_info "  • kubernetes/apps/${namespace}/bootstrap/"
            log_info "    ├── app/kustomization.yaml"
            log_info "    └── ks.yaml"
        fi
    done
    log_info ""
}

main() {
    log_info "🚀 Starting volsync SMB repository bootstrap setup..."
    log_info ""

    # Check prerequisites
    if ! check_prerequisites; then
        exit 1
    fi

    # Process each application namespace
    for namespace in "${APP_NAMESPACES[@]}"; do
        if [[ -d "${BASE_DIR}/${namespace}" ]]; then
            # Skip if bootstrap already exists and user doesn't want to overwrite
            if [[ -d "${BASE_DIR}/${namespace}/bootstrap" ]]; then
                log_warn "Bootstrap directory already exists for ${namespace}"
                read -p "Do you want to overwrite it? (y/N): " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    log_info "Skipping ${namespace}"
                    continue
                fi
            fi

            create_bootstrap_structure "${namespace}"
            update_namespace_kustomization "${namespace}"
        else
            log_warn "Namespace directory ${namespace} does not exist, skipping..."
        fi
    done

    show_summary

    log_info "✨ Bootstrap setup completed successfully!"
    log_info ""
    log_info "📋 Next steps:"
    log_info "1. Review the generated files"
    log_info "2. Commit and push the changes to your repository"
    log_info "3. Flux will automatically deploy the volsync-smb-repository PVC to each namespace"
    log_info "4. The PVC will depend on the SMB CSI driver being available"
    log_info ""
    log_info "💡 The volsync mutating admission policy will automatically inject the SMB repository"
    log_info "   mount into volsync jobs for backups."
    log_info ""
    log_info "🔍 You can check the status with:"
    log_info "   kubectl get pvc volsync-smb-repository -n <namespace>"
}

# Run the main function
main "$@"
