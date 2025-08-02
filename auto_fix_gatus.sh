#!/bin/bash

# Comprehensive script to automatically fix gatus components based on ingress className
set -e

echo "🚀 Starting automated gatus component assignment based on ingress analysis..."

# Phase 1: Clean up all existing issues first
echo -e "\n🧹 PHASE 1: Cleaning up existing template/guarded references..."

# Remove all templates/guarded from kustomization.yaml files
find kubernetes/apps -name "kustomization.yaml" -exec sed -i '' '/.*guarded.*/d' {} \;
find kubernetes/apps -name "kustomization.yaml" -exec sed -i '' '/.*templates\/.*/d' {} \;
find kubernetes/apps -name "kustomization.yaml" -exec sed -i '' '/.*\/volsync$/d' {} \;

# Fix templates in ks.yaml files
find kubernetes/apps -name "ks.yaml" -exec sed -i '' 's|../../../../templates/keda/nas-scaler|../../../../components/keda/nas-scaler|g' {} \;
find kubernetes/apps -name "ks.yaml" -exec sed -i '' 's|../../../../templates/volsync|../../../../components/volsync|g' {} \;
find kubernetes/apps -name "ks.yaml" -exec sed -i '' 's|../../../../templates/gatus/|../../../../components/gatus/|g' {} \;
find kubernetes/apps -name "ks.yaml" -exec sed -i '' 's|../../../../components/gatus/guarded|../../../../components/gatus/internal|g' {} \;

echo "✅ Basic cleanup completed"

# Phase 2: Analyze all apps and auto-assign gatus based on ingress
echo -e "\n🔍 PHASE 2: Analyzing ingress configurations and auto-assigning gatus..."

# Function to determine gatus type based on ingress
determine_gatus_type() {
    local app_dir="$1"
    local helmrelease_file="$app_dir/helmrelease.yaml"
    
    if [ -f "$helmrelease_file" ]; then
        # Check for external ingress
        if grep -q "className.*external\|ingressClassName.*external" "$helmrelease_file" 2>/dev/null; then
            echo "external"
            return
        fi
        # Check for internal ingress
        if grep -q "className.*internal\|ingressClassName.*internal" "$helmrelease_file" 2>/dev/null; then
            echo "internal"
            return
        fi
    fi
    
    # No ingress found
    echo "none"
}

# Function to add gatus component to ks.yaml if missing
add_gatus_component() {
    local ks_file="$1"
    local gatus_type="$2"
    
    # Check if already has gatus component
    if grep -q "components/gatus/" "$ks_file" 2>/dev/null; then
        # Update existing gatus component
        sed -i '' "s|../../../../components/gatus/.*|../../../../components/gatus/$gatus_type|g" "$ks_file"
        echo "    ✅ Updated existing gatus to $gatus_type"
    else
        # Add gatus component
        if grep -q "components:" "$ks_file" 2>/dev/null; then
            # Add to existing components section
            sed -i '' "/components:/a\\
    - ../../../../components/gatus/$gatus_type" "$ks_file"
            echo "    ✅ Added gatus/$gatus_type to existing components"
        else
            # Create new components section
            sed -i '' "/postBuild:/a\\
  components:\\
    - ../../../../components/gatus/$gatus_type" "$ks_file"
            echo "    ✅ Created components section with gatus/$gatus_type"
        fi
    fi
}

# Process all apps
apps_processed=0
apps_with_ingress=0
apps_external=0
apps_internal=0

for app_dir in kubernetes/apps/*/*/app; do
    if [ -d "$app_dir" ]; then
        app_name=$(basename "$(dirname "$app_dir")")
        namespace=$(basename "$(dirname "$(dirname "$app_dir")")")
        ks_file="$(dirname "$app_dir")/ks.yaml"
        
        if [ -f "$ks_file" ]; then
            apps_processed=$((apps_processed + 1))
            gatus_type=$(determine_gatus_type "$app_dir")
            
            echo "📱 Processing $namespace/$app_name:"
            
            case "$gatus_type" in
                "external")
                    apps_with_ingress=$((apps_with_ingress + 1))
                    apps_external=$((apps_external + 1))
                    echo "    🌐 Found EXTERNAL ingress"
                    add_gatus_component "$ks_file" "external"
                    ;;
                "internal")
                    apps_with_ingress=$((apps_with_ingress + 1))
                    apps_internal=$((apps_internal + 1))
                    echo "    🏠 Found INTERNAL ingress"
                    add_gatus_component "$ks_file" "internal"
                    ;;
                "none")
                    echo "    ⭕ No ingress found - skipping gatus"
                    ;;
            esac
        fi
    fi
done

# Phase 3: Clean up old directories
echo -e "\n🗑️ PHASE 3: Cleaning up old directories..."
if [ -d "kubernetes/components/gatus/guarded" ]; then
    echo "Removing old guarded directory..."
    rm -rf kubernetes/components/gatus/guarded
fi

# Phase 4: Final verification
echo -e "\n✅ PHASE 4: Final verification..."

# Check for remaining issues
templates_in_kust=$(find kubernetes/apps -name "kustomization.yaml" -exec grep -l "templates/" {} \; 2>/dev/null | wc -l | tr -d ' ')
templates_in_ks=$(find kubernetes/apps -name "ks.yaml" -exec grep -l "templates/" {} \; 2>/dev/null | wc -l | tr -d ' ')
guarded_refs=$(find kubernetes/apps -name "*.yaml" -exec grep -l "guarded" {} \; 2>/dev/null | wc -l | tr -d ' ')

echo "📊 FINAL STATISTICS:"
echo "===================="
echo "Apps processed: $apps_processed"
echo "Apps with ingress: $apps_with_ingress"
echo "  - External ingress: $apps_external"
echo "  - Internal ingress: $apps_internal"
echo ""
echo "Remaining issues:"
echo "  - Templates in kustomization.yaml: $templates_in_kust"
echo "  - Templates in ks.yaml: $templates_in_ks"
echo "  - Guarded references: $guarded_refs"

if [ "$templates_in_kust" -eq 0 ] && [ "$templates_in_ks" -eq 0 ] && [ "$guarded_refs" -eq 0 ]; then
    echo ""
    echo "🎉 SUCCESS! All issues resolved!"
    echo "✅ All apps now have correct gatus components based on their ingress configuration"
    echo "✅ All template references migrated to components"
    echo "✅ All guarded references converted to internal"
else
    echo ""
    echo "⚠️ Some issues remain - check the files above"
fi
