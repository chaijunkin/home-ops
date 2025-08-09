#!/bin/bash

# Script to add targetNamespace to Kustomization files that don't have it
# The targetNamespace will be set to the namespace directory the app is in

set -euo pipefail

# Files that need targetNamespace added
files_without_target_namespace=(
    "/Users/jkchai/Documents/CODE/APP/home-ops/kubernetes/apps/flux-system/headlamp/ks.yaml"
    "/Users/jkchai/Documents/CODE/APP/home-ops/kubernetes/apps/network/external-services/ks.yaml"
    "/Users/jkchai/Documents/CODE/APP/home-ops/kubernetes/apps/default/cyberchef/ks.yaml"
    "/Users/jkchai/Documents/CODE/APP/home-ops/kubernetes/apps/default/homepage/ks.yaml"
    "/Users/jkchai/Documents/CODE/APP/home-ops/kubernetes/apps/default/searxng/ks.yaml"
    "/Users/jkchai/Documents/CODE/APP/home-ops/kubernetes/apps/default/excalidraw/ks.yaml"
    "/Users/jkchai/Documents/CODE/APP/home-ops/kubernetes/apps/default/privatebin/ks.yaml"
    "/Users/jkchai/Documents/CODE/APP/home-ops/kubernetes/apps/default/miniflux/ks.yaml"
    "/Users/jkchai/Documents/CODE/APP/home-ops/kubernetes/apps/default/it-tools/ks.yaml"
    "/Users/jkchai/Documents/CODE/APP/home-ops/kubernetes/apps/media/minio/ks.yaml"
)

# Function to extract namespace from file path
get_namespace_from_path() {
    local file_path="$1"
    # Extract namespace from path: kubernetes/apps/NAMESPACE/app/ks.yaml
    echo "$file_path" | sed -n 's|.*/kubernetes/apps/\([^/]*\)/.*|\1|p'
}

# Function to add targetNamespace after spec:
add_target_namespace() {
    local file_path="$1"
    local namespace="$2"

    echo "Processing: $file_path (namespace: $namespace)"

    # Check if file exists
    if [[ ! -f "$file_path" ]]; then
        echo "Warning: File not found: $file_path"
        return 1
    fi

    # Check if targetNamespace already exists
    if grep -q "targetNamespace:" "$file_path"; then
        echo "  -> targetNamespace already exists, skipping"
        return 0
    fi

    # Create a temporary file
    local temp_file=$(mktemp)

    # Add targetNamespace after spec: line
    awk -v ns="$namespace" '
    /^spec:$/ {
        print $0
        print "  targetNamespace: " ns
        next
    }
    { print }
    ' "$file_path" > "$temp_file"

    # Replace original file with modified content
    mv "$temp_file" "$file_path"

    echo "  -> Added targetNamespace: $namespace"
}

# Main execution
echo "Adding targetNamespace to Kustomization files..."
echo "================================================"

for file_path in "${files_without_target_namespace[@]}"; do
    namespace=$(get_namespace_from_path "$file_path")

    if [[ -z "$namespace" ]]; then
        echo "Warning: Could not extract namespace from path: $file_path"
        continue
    fi

    add_target_namespace "$file_path" "$namespace"
    echo
done

echo "Script completed!"
echo
echo "Summary of changes made:"
echo "- Added targetNamespace to ${#files_without_target_namespace[@]} files"
echo "- Each targetNamespace was set to match the namespace directory"
echo
echo "You can now review the changes with:"
echo "git diff"
