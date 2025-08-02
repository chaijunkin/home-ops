#!/bin/bash

# Script to add VolSync component to applications that use existingClaim with *app pattern
# Usage: ./add-volsync-component.sh [--dry-run]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
KUBERNETES_APPS_DIR="$REPO_ROOT/kubernetes/apps"

# Check if dry-run mode
DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo -e "${YELLOW}Running in dry-run mode${NC}"
fi

# Function to log messages
log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if existingClaim uses *app pattern
has_existing_claim_app_pattern() {
    local file="$1"
    # Look for patterns like:
    # existingClaim: *app
    # existingClaim: "*app"
    # existingClaim: *appname
    grep -qE "existingClaim:\s*[\"']?\*[a-zA-Z-]*app[a-zA-Z-]*[\"']?" "$file" 2>/dev/null
}

# Function to check if volsync component is already added
has_volsync_component() {
    local kustomization_file="$1"
    if [[ ! -f "$kustomization_file" ]]; then
        return 1
    fi
    grep -qE "^\s*-\s+.*components/volsync" "$kustomization_file" 2>/dev/null
}

# Function to add volsync component to kustomization.yaml
add_volsync_component() {
    local kustomization_file="$1"
    local app_path="$2"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "Would add VolSync component to: $kustomization_file"
        return 0
    fi
    
    # Check if components section exists
    if grep -q "^components:" "$kustomization_file"; then
        # Add to existing components section
        sed -i '/^components:/a\  - ../../../../components/volsync' "$kustomization_file"
    else
        # Check if resources section exists to add components before it
        if grep -q "^resources:" "$kustomization_file"; then
            sed -i '/^resources:/i\components:\n  - ../../../../components/volsync\n' "$kustomization_file"
        else
            # Add components section at the end
            echo -e "\ncomponents:\n  - ../../../../components/volsync" >> "$kustomization_file"
        fi
    fi
    
    log_success "Added VolSync component to $app_path"
}

# Function to process a single app directory
process_app() {
    local app_dir="$1"
    local namespace=$(basename "$(dirname "$app_dir")")
    local app_name=$(basename "$app_dir")
    local relative_path="$namespace/$app_name"
    
    log "Processing app: $relative_path"
    
    # Look for helmrelease.yaml or hr.yaml files recursively
    local helmrelease_files=()
    while IFS= read -r -d '' file; do
        helmrelease_files+=("$file")
    done < <(find "$app_dir" -name "helmrelease.yaml" -o -name "hr.yaml" -print0 2>/dev/null || true)
    
    if [[ ${#helmrelease_files[@]} -eq 0 ]]; then
        log_warning "No HelmRelease files found in $relative_path"
        return 0
    fi
    
    # Check each HelmRelease file for existingClaim pattern
    local found_pattern=false
    local found_file=""
    for hr_file in "${helmrelease_files[@]}"; do
        if has_existing_claim_app_pattern "$hr_file"; then
            log "Found existingClaim pattern in: $hr_file"
            found_pattern=true
            found_file="$hr_file"
            break
        fi
    done
    
    if [[ "$found_pattern" == "false" ]]; then
        log "No existingClaim pattern found in $relative_path"
        return 0
    fi
    
    # Check if kustomization.yaml exists in the app root directory
    local kustomization_file="$app_dir/kustomization.yaml"
    if [[ ! -f "$kustomization_file" ]]; then
        log_warning "No kustomization.yaml found in $relative_path"
        return 0
    fi
    
    # Check if VolSync component is already added
    if has_volsync_component "$kustomization_file"; then
        log "VolSync component already exists in $relative_path"
        return 0
    fi
    
    # Show which file triggered the addition
    log "Pattern found in: $(echo "$found_file" | sed "s|$app_dir/||")"
    
    # Add the VolSync component
    add_volsync_component "$kustomization_file" "$relative_path"
}

# Main function
main() {
    log "Starting VolSync component addition script"
    log "Searching in: $KUBERNETES_APPS_DIR"
    
    if [[ ! -d "$KUBERNETES_APPS_DIR" ]]; then
        log_error "Kubernetes apps directory not found: $KUBERNETES_APPS_DIR"
        exit 1
    fi
    
    # Find all app directories (directories that contain kustomization.yaml or helmrelease.yaml)
    local processed_count=0
    local added_count=0
    
    # Iterate through namespace directories
    for namespace_dir in "$KUBERNETES_APPS_DIR"/*; do
        if [[ ! -d "$namespace_dir" ]]; then
            continue
        fi
        
        local namespace=$(basename "$namespace_dir")
        log "Checking namespace: $namespace"
        
        # Iterate through app directories in namespace
        for app_dir in "$namespace_dir"/*; do
            if [[ ! -d "$app_dir" ]]; then
                continue
            fi
            
            # Skip if no kustomization.yaml exists
            if [[ ! -f "$app_dir/kustomization.yaml" ]]; then
                continue
            fi
            
            processed_count=$((processed_count + 1))
            
            # Process the app
            if process_app "$app_dir"; then
                # Check if we actually added something (only in non-dry-run mode)
                if [[ "$DRY_RUN" == "false" ]] && has_volsync_component "$app_dir/kustomization.yaml"; then
                    added_count=$((added_count + 1))
                fi
            fi
        done
    done
    
    log_success "Script completed!"
    log "Processed $processed_count applications"
    if [[ "$DRY_RUN" == "false" ]]; then
        log "Added VolSync component to $added_count applications"
    else
        log "Dry-run completed - no changes made"
    fi
}

# Run the script
main "$@"
