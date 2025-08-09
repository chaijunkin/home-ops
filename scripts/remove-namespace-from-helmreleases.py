#!/usr/bin/env python3
"""
Script to remove 'namespace' field from all HelmRelease files.
This script preserves the YAML structure and comments.
"""

import os
import sys
import glob
import ruamel.yaml
from pathlib import Path

def remove_namespace_from_helmrelease(file_path):
    """Remove namespace field from a HelmRelease YAML file."""
    try:
        yaml = ruamel.yaml.YAML()
        yaml.preserve_quotes = True
        yaml.width = 4096  # Prevent line wrapping
        yaml.indent(mapping=2, sequence=4, offset=2)

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.strip():
            print(f"⚠️  Skipping {file_path}: Empty file")
            return False

        # Handle multi-document YAML files
        documents = []
        modified = False

        for doc in yaml.load_all(content):
            if doc is None:
                continue

            # Check if this is a HelmRelease and has a namespace
            if (doc.get('kind') == 'HelmRelease' and
                'metadata' in doc and
                'namespace' in doc['metadata']):

                # Store the namespace value for logging
                namespace_value = doc['metadata']['namespace']

                # Remove the namespace field
                del doc['metadata']['namespace']
                modified = True

                print(f"✅ {file_path}: Removed namespace '{namespace_value}' from HelmRelease")

            documents.append(doc)

        if not modified:
            # Check if file contains any HelmRelease
            has_helmrelease = any(doc.get('kind') == 'HelmRelease' for doc in documents if doc)
            if has_helmrelease:
                print(f"ℹ️  {file_path}: No namespace field found in HelmRelease")
            else:
                print(f"ℹ️  Skipping {file_path}: No HelmRelease resource found")
            return False

        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            for i, doc in enumerate(documents):
                if i > 0:
                    f.write('---\n')
                yaml.dump(doc, f)

        return True

    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return False

def main():
    """Main function to process all HelmRelease files."""

    # Get the workspace root directory
    workspace_root = Path("/Users/jkchai/Documents/CODE/APP/home-ops")

    if not workspace_root.exists():
        print(f"❌ Workspace directory not found: {workspace_root}")
        sys.exit(1)

    # Find all helmrelease.yaml files
    helmrelease_patterns = [
        "**/helmrelease.yaml",
        "**/HelmRelease.yaml",
        "**/helm-release.yaml"
    ]

    helmrelease_files = []
    for pattern in helmrelease_patterns:
        full_pattern = str(workspace_root / pattern)
        helmrelease_files.extend(glob.glob(full_pattern, recursive=True))

    # Remove duplicates and filter out .archive directories
    helmrelease_files = list(set(helmrelease_files))
    helmrelease_files = [f for f in helmrelease_files if "/.archive/" not in f]

    if not helmrelease_files:
        print("ℹ️  No HelmRelease files found")
        return

    print(f"🔍 Found {len(helmrelease_files)} HelmRelease files")
    print()

    # Ask for confirmation
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        print("🧪 DRY RUN MODE - No files will be modified")
        dry_run = True
    else:
        response = input("Do you want to proceed with removing namespace fields from HelmRelease files? (y/N): ")
        if response.lower() != 'y':
            print("❌ Operation cancelled")
            return
        dry_run = False

    # Process each file
    modified_count = 0
    for file_path in sorted(helmrelease_files):
        relative_path = Path(file_path).relative_to(workspace_root)
        print(f"📝 Processing: {relative_path}")

        if not dry_run:
            if remove_namespace_from_helmrelease(file_path):
                modified_count += 1
        else:
            # In dry run mode, just check if namespace exists
            try:
                yaml = ruamel.yaml.YAML()
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                found_helmrelease_with_namespace = False
                for doc in yaml.load_all(content):
                    if (doc and
                        doc.get('kind') == 'HelmRelease' and
                        'metadata' in doc and
                        'namespace' in doc['metadata']):
                        print(f"🔍 Would remove namespace '{doc['metadata']['namespace']}' from {relative_path}")
                        found_helmrelease_with_namespace = True
                        break

                if found_helmrelease_with_namespace:
                    modified_count += 1
                else:
                    # Check if file contains any HelmRelease
                    has_helmrelease = False
                    for doc in yaml.load_all(content):
                        if doc and doc.get('kind') == 'HelmRelease':
                            has_helmrelease = True
                            break

                    if has_helmrelease:
                        print(f"ℹ️  No namespace field in HelmRelease in {relative_path}")
                    else:
                        print(f"ℹ️  No HelmRelease resource in {relative_path}")

            except Exception as e:
                print(f"❌ Error reading {relative_path}: {e}")

    print()
    if dry_run:
        print(f"🧪 DRY RUN COMPLETE: {modified_count} HelmRelease files would be modified")
        print("Run without --dry-run to actually modify the files")
    else:
        print(f"✅ COMPLETE: Modified {modified_count} HelmRelease files")

if __name__ == "__main__":
    main()
