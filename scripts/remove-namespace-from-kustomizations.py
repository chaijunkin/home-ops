#!/usr/bin/env python3
"""
Script to remove 'namespace' field from all kustomization.yaml files in app folders.
This script preserves the YAML structure and comments.
"""

import os
import sys
import glob
import ruamel.yaml
from pathlib import Path

def remove_namespace_from_kustomization(file_path):
    """Remove namespace field from a kustomization.yaml file."""
    try:
        yaml = ruamel.yaml.YAML()
        yaml.preserve_quotes = True
        yaml.width = 4096  # Prevent line wrapping
        yaml.indent(mapping=2, sequence=4, offset=2)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = yaml.load(f)
        
        if content is None:
            print(f"⚠️  Skipping {file_path}: Empty or invalid YAML")
            return False
            
        # Check if namespace field exists
        if 'namespace' not in content:
            print(f"ℹ️  {file_path}: No namespace field found")
            return False
            
        # Store the namespace value for logging
        namespace_value = content['namespace']
        
        # Remove the namespace field
        del content['namespace']
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(content, f)
            
        print(f"✅ {file_path}: Removed namespace '{namespace_value}'")
        return True
        
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return False

def main():
    """Main function to process all kustomization.yaml files in app folders."""
    
    # Get the workspace root directory
    workspace_root = Path("/Users/jkchai/Documents/CODE/APP/home-ops")
    
    if not workspace_root.exists():
        print(f"❌ Workspace directory not found: {workspace_root}")
        sys.exit(1)
        
    # Find all kustomization.yaml files in app folders
    pattern = str(workspace_root / "**/app/kustomization.yaml")
    kustomization_files = glob.glob(pattern, recursive=True)
    
    # Filter out .archive directories
    kustomization_files = [f for f in kustomization_files if "/.archive/" not in f]
    
    if not kustomization_files:
        print("ℹ️  No kustomization.yaml files found in app folders")
        return
        
    print(f"🔍 Found {len(kustomization_files)} kustomization.yaml files in app folders")
    print()
    
    # Ask for confirmation
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        print("🧪 DRY RUN MODE - No files will be modified")
        dry_run = True
    else:
        response = input("Do you want to proceed with removing namespace fields? (y/N): ")
        if response.lower() != 'y':
            print("❌ Operation cancelled")
            return
        dry_run = False
    
    # Process each file
    modified_count = 0
    for file_path in sorted(kustomization_files):
        relative_path = Path(file_path).relative_to(workspace_root)
        print(f"📝 Processing: {relative_path}")
        
        if not dry_run:
            if remove_namespace_from_kustomization(file_path):
                modified_count += 1
        else:
            # In dry run mode, just check if namespace exists
            try:
                yaml = ruamel.yaml.YAML()
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = yaml.load(f)
                if content and 'namespace' in content:
                    print(f"🔍 Would remove namespace '{content['namespace']}' from {relative_path}")
                    modified_count += 1
                else:
                    print(f"ℹ️  No namespace field in {relative_path}")
            except Exception as e:
                print(f"❌ Error reading {relative_path}: {e}")
    
    print()
    if dry_run:
        print(f"🧪 DRY RUN COMPLETE: {modified_count} files would be modified")
        print("Run without --dry-run to actually modify the files")
    else:
        print(f"✅ COMPLETE: Modified {modified_count} files")

if __name__ == "__main__":
    main()
