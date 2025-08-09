#!/usr/bin/env python3
"""
Script to add missing namespace fields to dependsOn entries in Kustomization files.

This script finds dependencies that are missing their namespace field and adds them
based on a predefined mapping.
"""

import os
import yaml
import glob
from pathlib import Path

# Mapping of dependencies to their correct namespaces
DEPENDENCY_NAMESPACES = {
    # Database dependencies
    'cloudnative-pg': 'database',
    'cloudnative-pg-cluster': 'database',
    'dragonfly-cluster': 'database',
    'dragonfly-operator': 'database',
    
    # External secrets dependencies
    'external-secrets': 'kube-system',
    'external-secrets-stores': 'kube-system',
    'external-secrets-cluster-secrets': 'kube-system',
    'external-secrets-bitwarden': 'kube-system',
    
    # System dependencies
    'csi-driver-smb': 'kube-system',
    'cert-manager': 'cert-manager',
    
    # Flux dependencies
    'flux-operator': 'flux-system',
    'flux-instance': 'flux-system',
}

def safe_load_yaml(content):
    """Load YAML content safely, handling multiple documents."""
    documents = []
    try:
        for doc in yaml.safe_load_all(content):
            if doc is not None:
                documents.append(doc)
        return documents
    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}")
        return None

def safe_dump_yaml(documents):
    """Dump YAML documents safely."""
    result = ""
    for i, doc in enumerate(documents):
        if i > 0:
            result += "---\n"
        result += yaml.dump(doc, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return result

def fix_dependency_namespaces(file_path, dry_run=False):
    """Fix missing namespace fields in a single kustomization file."""
    print(f"Processing: {file_path}")
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        documents = safe_load_yaml(content)
        if documents is None:
            print(f"  Skipped - could not parse YAML")
            return False
        
        modified = False
        changes = []
        
        for doc in documents:
            if (doc.get('kind') == 'Kustomization' and 
                doc.get('apiVersion') == 'kustomize.toolkit.fluxcd.io/v1'):
                
                spec = doc.get('spec', {})
                depends_on = spec.get('dependsOn', [])
                
                if depends_on:
                    for dep in depends_on:
                        dep_name = dep.get('name')
                        current_namespace = dep.get('namespace')
                        
                        # If dependency is missing namespace field and we know its namespace
                        if current_namespace is None and dep_name in DEPENDENCY_NAMESPACES:
                            correct_namespace = DEPENDENCY_NAMESPACES[dep_name]
                            change_msg = f"Adding namespace to {dep_name}: -> {correct_namespace}"
                            changes.append(change_msg)
                            print(f"  {change_msg}")
                            
                            if not dry_run:
                                dep['namespace'] = correct_namespace
                            modified = True
                        
                        # If dependency has wrong namespace, update it
                        elif (current_namespace is not None and 
                              dep_name in DEPENDENCY_NAMESPACES and
                              current_namespace != DEPENDENCY_NAMESPACES[dep_name]):
                            correct_namespace = DEPENDENCY_NAMESPACES[dep_name]
                            change_msg = f"Updating {dep_name}: {current_namespace} -> {correct_namespace}"
                            changes.append(change_msg)
                            print(f"  {change_msg}")
                            
                            if not dry_run:
                                dep['namespace'] = correct_namespace
                            modified = True
        
        if modified and not dry_run:
            # Write the updated content
            new_content = safe_dump_yaml(documents)
            
            # Preserve the original formatting as much as possible
            if content.startswith('---\n'):
                new_content = '---\n' + new_content
            
            with open(file_path, 'w') as f:
                f.write(new_content)
            
            print(f"  Updated successfully")
        elif modified and dry_run:
            print(f"  Would be updated (dry-run)")
        else:
            print(f"  No changes needed")
        
        return modified
    
    except Exception as e:
        print(f"  Error: {e}")
        return False

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix missing namespace fields in dependencies')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be changed without making changes')
    
    args = parser.parse_args()
    
    # Get the base path for the kubernetes apps
    script_dir = Path(__file__).parent
    base_path = script_dir.parent / "kubernetes" / "apps"
    
    if not base_path.exists():
        print(f"Error: Base path {base_path} does not exist")
        return 1
    
    print(f"Base path: {base_path}")
    if args.dry_run:
        print("DRY-RUN MODE: No files will be modified")
    
    # Find all kustomization files
    ks_files = glob.glob(os.path.join(str(base_path), "**/ks.yaml"), recursive=True)
    
    total_files = len(ks_files)
    updated_files = 0
    
    print(f"\nProcessing {total_files} kustomization files...")
    
    for ks_file in ks_files:
        if fix_dependency_namespaces(ks_file, args.dry_run):
            updated_files += 1
    
    print(f"\nSummary:")
    print(f"  Total files processed: {total_files}")
    if args.dry_run:
        print(f"  Files that would be updated: {updated_files}")
        print(f"  Files that would remain unchanged: {total_files - updated_files}")
    else:
        print(f"  Files updated: {updated_files}")
        print(f"  Files unchanged: {total_files - updated_files}")
    
    return 0

if __name__ == "__main__":
    exit(main())
