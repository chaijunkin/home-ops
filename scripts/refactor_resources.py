import os
from ruamel.yaml import YAML

def refactor_resources(resources):
    """
    Refactor resources according to rules:
    - Keep memory limits (or set default if missing)
    - Remove CPU limits
    - Remove memory requests
    - Set CPU requests to 10m (minimal)
    """
    changed = False

    # Remove memory requests
    if 'requests' in resources and 'memory' in resources['requests']:
        del resources['requests']['memory']
        changed = True

    # Remove cpu limits
    if 'limits' in resources and 'cpu' in resources['limits']:
        del resources['limits']['cpu']
        changed = True

    # Ensure memory limits exists (set default if missing)
    if 'limits' not in resources:
        resources['limits'] = {}
    if 'memory' not in resources['limits']:
        resources['limits']['memory'] = '512Mi'
        changed = True

    # Set CPU requests to minimal 10m
    if 'requests' not in resources:
        resources['requests'] = {}
    if 'cpu' not in resources['requests']:
        resources['requests']['cpu'] = '10m'
        changed = True
    elif resources['requests']['cpu'] != '10m':
        resources['requests']['cpu'] = '10m'
        changed = True

    # Clean up empty sections
    if 'requests' in resources and not resources['requests']:
        del resources['requests']
        changed = True
    if 'limits' in resources and not resources['limits']:
        del resources['limits']
        changed = True

    return changed

def process_yaml_file(filepath):
    # Only process HelmRelease files
    if not ('helmrelease.yaml' in filepath.lower() or 'helmrelease.yml' in filepath.lower()):
        return

    try:
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.width = 4096  # Prevent line wrapping

        with open(filepath, 'r') as f:
            docs = list(yaml.load_all(f))

        changed = False

        def recursive_search(obj):
            nonlocal changed

            def is_container_resources(parent_obj):
                # Check if this resources block is in a container context
                return ('image' in parent_obj or
                        'env' in parent_obj or
                        'ports' in parent_obj or
                        'command' in parent_obj or
                        'args' in parent_obj)

            if hasattr(obj, 'items'):  # dict-like object
                keys_to_remove = []
                for k, v in obj.items():
                    # Only process resources in containers context
                    if (k == 'resources' and hasattr(v, 'items') and
                        is_container_resources(obj)):
                        resource_changed = refactor_resources(v)
                        if resource_changed:
                            changed = True
                        # Remove resources if now empty
                        if not v:
                            keys_to_remove.append(k)
                    else:
                        recursive_search(v)

                # Remove empty resources blocks
                for key in keys_to_remove:
                    del obj[key]
                    changed = True

            elif hasattr(obj, '__iter__') and not isinstance(obj, str):  # list-like object
                for item in obj:
                    recursive_search(item)

        for doc in docs:
            if doc and hasattr(doc, 'get'):
                # Only process if it's actually a HelmRelease
                if doc.get('kind') == 'HelmRelease':
                    recursive_search(doc)

        if changed:
            with open(filepath, 'w') as f:
                yaml.dump_all(docs, f)
            print(f"Refactored: {filepath}")

    except Exception as e:
        print(f"Error processing {filepath}: {e}")

def process_dir(root_dir):
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.yaml') or filename.endswith('.yml'):
                process_yaml_file(os.path.join(dirpath, filename))

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python refactor_resources.py <directory>")
        print("Rules applied:")
        print("- Keep memory limits (set 512Mi if missing)")
        print("- Remove CPU limits")
        print("- Remove memory requests")
        print("- Set CPU requests to 10m")
        print("- Remove empty resources blocks")
        sys.exit(1)

    process_dir(sys.argv[1])