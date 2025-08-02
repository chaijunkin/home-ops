#!/bin/bash

# Script to fix missing APP variable in ks.yaml postBuild.substitute sections
set -e

echo "🔧 Fixing missing APP variable in ks.yaml files..."

# Function to add APP variable to postBuild section
fix_app_variable() {
    local ks_file="$1"
    local app_name="$2"
    
    echo "  📝 Processing $app_name..."
    
    # Check if postBuild section exists
    if grep -q "postBuild:" "$ks_file"; then
        # Check if substitute section exists
        if grep -q "substitute:" "$ks_file"; then
            # Check if APP variable already exists
            if ! grep -q "APP:" "$ks_file"; then
                # Add APP variable to existing substitute section
                sed -i '' "/substitute:/a\\
      APP: *app" "$ks_file"
                echo "    ✅ Added APP variable to existing substitute section"
            else
                echo "    ✅ APP variable already exists"
            fi
        else
            # Add substitute section with APP variable
            sed -i '' "/postBuild:/a\\
    substitute:\\
      APP: *app" "$ks_file"
            echo "    ✅ Added substitute section with APP variable"
        fi
    else
        # Add entire postBuild section with APP variable
        # Find the line before components: or at the end of spec:
        if grep -q "components:" "$ks_file"; then
            sed -i '' "/components:/i\\
  postBuild:\\
    substitute:\\
      APP: *app" "$ks_file"
        else
            # Add before the end of spec
            sed -i '' "/^spec:/,/^[^[:space:]]/{
                /^[^[:space:]]/i\
  postBuild:\
    substitute:\
      APP: *app
            }" "$ks_file"
        fi
        echo "    ✅ Added complete postBuild section with APP variable"
    fi
}

# Process all ks.yaml files that have gatus components but potentially missing APP variable
apps_fixed=0
apps_skipped=0

echo -e "\n🔍 Scanning for ks.yaml files with gatus components..."

for ks_file in $(find kubernetes/apps -name "ks.yaml" -exec grep -l "components/gatus/" {} \;); do
    # Extract app name from the file
    app_name=$(grep "name: &app" "$ks_file" | sed 's/.*&app //' | tr -d ' ')
    
    if [ -z "$app_name" ]; then
        echo "⚠️  Could not extract app name from $ks_file - skipping"
        apps_skipped=$((apps_skipped + 1))
        continue
    fi
    
    # Check if APP variable is missing or if postBuild section is missing
    if ! grep -q "APP:" "$ks_file" || ! grep -q "postBuild:" "$ks_file"; then
        fix_app_variable "$ks_file" "$app_name"
        apps_fixed=$((apps_fixed + 1))
    else
        echo "  ✅ $app_name already has APP variable"
        apps_skipped=$((apps_skipped + 1))
    fi
done

echo -e "\n📊 SUMMARY:"
echo "==========="
echo "Apps fixed: $apps_fixed"
echo "Apps skipped (already correct): $apps_skipped"

# Verification
echo -e "\n🔍 Verification - checking for potential issues..."

# Check for any ks.yaml files with gatus components but no APP variable
missing_app_vars=$(find kubernetes/apps -name "ks.yaml" -exec grep -l "components/gatus/" {} \; | xargs grep -L "APP:" | wc -l | tr -d ' ')

if [ "$missing_app_vars" -eq "0" ]; then
    echo "✅ All ks.yaml files with gatus components now have APP variable!"
else
    echo "❌ Still found $missing_app_vars files missing APP variable:"
    find kubernetes/apps -name "ks.yaml" -exec grep -l "components/gatus/" {} \; | xargs grep -L "APP:"
fi

echo -e "\n🎉 Fix completed! The ConfigMap naming issue should now be resolved."
