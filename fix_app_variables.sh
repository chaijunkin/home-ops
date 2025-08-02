#!/bin/bash

# Script to fix missing APP variables in ks.yaml files that have gatus components
set -e

echo "🔍 Checking for ks.yaml files with gatus components but missing APP variable..."

# Function to check if file has gatus component but missing APP variable
check_and_fix_app_variable() {
    local ks_file="$1"
    
    # Check if file has gatus component
    if grep -q "components/gatus/" "$ks_file" 2>/dev/null; then
        # Check if it has postBuild.substitute.APP
        if ! grep -A 10 "postBuild:" "$ks_file" 2>/dev/null | grep -q "APP:" 2>/dev/null; then
            echo "❌ Missing APP variable: $ks_file"
            
            # Extract app name from metadata.name
            app_name=$(grep "name: " "$ks_file" | head -1 | sed 's/.*name: *//; s/&app *//')
            
            # Check if it has postBuild section
            if grep -q "postBuild:" "$ks_file" 2>/dev/null; then
                # Add APP to existing postBuild section
                if grep -A 5 "postBuild:" "$ks_file" | grep -q "substitute:" 2>/dev/null; then
                    # Add to existing substitute section
                    sed -i '' "/substitute:/a\\
      APP: *app" "$ks_file"
                    echo "  ✅ Added APP to existing substitute section"
                else
                    # Add substitute section to postBuild
                    sed -i '' "/postBuild:/a\\
    substitute:\\
      APP: *app" "$ks_file"
                    echo "  ✅ Added substitute section with APP"
                fi
            else
                # Add entire postBuild section before components
                sed -i '' "/components:/i\\
  postBuild:\\
    substitute:\\
      APP: *app" "$ks_file"
                echo "  ✅ Added postBuild section with APP"
            fi
            
            # Also ensure it uses &app anchor
            if ! grep -q "name: &app" "$ks_file" 2>/dev/null; then
                sed -i '' "s/name: $app_name/name: \&app $app_name/" "$ks_file"
                echo "  ✅ Added &app anchor to metadata.name"
            fi
            
            return 1  # Found and fixed an issue
        else
            echo "✅ APP variable present: $ks_file"
            return 0  # No issue
        fi
    fi
    return 0  # No gatus component, so no issue
}

# Process all ks.yaml files
issues_found=0
issues_fixed=0

echo "Processing ks.yaml files..."
for ks_file in $(find kubernetes/apps -name "ks.yaml"); do
    if check_and_fix_app_variable "$ks_file"; then
        # No issues
        :
    else
        issues_found=$((issues_found + 1))
        issues_fixed=$((issues_fixed + 1))
    fi
done

echo ""
echo "📊 RESULTS:"
echo "==========="
echo "Issues found and fixed: $issues_fixed"

# Final verification
echo ""
echo "🔍 Final verification - checking for remaining issues..."
remaining_issues=0

for ks_file in $(find kubernetes/apps -name "ks.yaml"); do
    if grep -q "components/gatus/" "$ks_file" 2>/dev/null; then
        if ! grep -A 10 "postBuild:" "$ks_file" 2>/dev/null | grep -q "APP:" 2>/dev/null; then
            echo "❌ Still missing APP variable: $ks_file"
            remaining_issues=$((remaining_issues + 1))
        fi
    fi
done

if [ $remaining_issues -eq 0 ]; then
    echo "🎉 SUCCESS! All ks.yaml files with gatus components now have APP variable!"
else
    echo "⚠️ Warning: $remaining_issues files still have issues"
fi
