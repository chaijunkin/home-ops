import os

from ruamel.yaml import YAML


def refactor_resources(resources):
    """
    Refactor resources according to rules:
    - Keep memory limits (or set default if missing)
    - Remove CPU limits
    - Set memory requests to 150Mi (default)
    - Set CPU requests to 10m (minimal)
    """
    changed = False

    # Remove cpu limits
    if "limits" in resources and "cpu" in resources["limits"]:
        del resources["limits"]["cpu"]
        changed = True

    # Ensure memory limits exists (set default if missing)
    if "limits" not in resources:
        resources["limits"] = {}
    if "memory" not in resources["limits"]:
        resources["limits"]["memory"] = "512Mi"
        changed = True

    # Set CPU requests to minimal 10m
    if "requests" not in resources:
        resources["requests"] = {}
    if "cpu" not in resources["requests"]:
        resources["requests"]["cpu"] = "10m"
        changed = True
    elif resources["requests"]["cpu"] != "10m":
        resources["requests"]["cpu"] = "10m"
        changed = True

    # Set memory requests to 50Mi (default)
    if "memory" not in resources["requests"]:
        resources["requests"]["memory"] = "50Mi"
        changed = True
    elif resources["requests"]["memory"] != "50Mi":
        resources["requests"]["memory"] = "50Mi"
        changed = True

    # Clean up empty sections
    if "requests" in resources and not resources["requests"]:
        del resources["requests"]
        changed = True
    if "limits" in resources and not resources["limits"]:
        del resources["limits"]
        changed = True

    return changed


def process_yaml_file(filepath):
    # Only process HelmRelease files
    if not (
        "helmrelease.yaml" in filepath.lower() or "helmrelease.yml" in filepath.lower()
    ):
        return

    try:
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.width = 4096  # Prevent line wrapping

        with open(filepath, "r") as f:
            docs = list(yaml.load_all(f))

        changed = False

        def recursive_search(obj):
            nonlocal changed

            def is_container_resources(parent_obj):
                # Check if this resources block is in a container context
                return (
                    "image" in parent_obj
                    or "env" in parent_obj
                    or "ports" in parent_obj
                    or "command" in parent_obj
                    or "args" in parent_obj
                )

            def is_valid_resources_block(resources_obj):
                # Check if this looks like a valid Kubernetes resources block
                if not hasattr(resources_obj, "items"):
                    return False

                valid_keys = {"requests", "limits"}
                resource_keys = set(resources_obj.keys())

                # Must contain only valid resource keys
                if not resource_keys.issubset(valid_keys):
                    return False

                # Check if requests/limits contain valid resource types
                for section in resources_obj.values():
                    if hasattr(section, "items"):
                        valid_resource_types = {"cpu", "memory", "storage", "ephemeral-storage"}
                        if not set(section.keys()).issubset(valid_resource_types):
                            return False

                return True

            if hasattr(obj, "items"):  # dict-like object
                keys_to_remove = []
                for k, v in obj.items():
                    # Process resources blocks that are either:
                    # 1. In container contexts, OR
                    # 2. Valid Kubernetes resource specifications (Helm chart values)
                    if (
                        k == "resources"
                        and is_valid_resources_block(v)
                        and (is_container_resources(obj) or not is_container_resources(obj))
                    ):
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

            elif hasattr(obj, "__iter__") and not isinstance(
                obj, str
            ):  # list-like object
                for item in obj:
                    recursive_search(item)

        for doc in docs:
            if doc and hasattr(doc, "get"):
                # Only process if it's actually a HelmRelease
                if doc.get("kind") == "HelmRelease":
                    recursive_search(doc)

        if changed:
            with open(filepath, "w") as f:
                yaml.dump_all(docs, f)
            print(f"Refactored: {filepath}")

    except Exception as e:
        print(f"Error processing {filepath}: {e}")


def process_dir(root_dir):
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                process_yaml_file(os.path.join(dirpath, filename))


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python refactor_resources.py <directory>")
        print("Rules applied to all Kubernetes resources blocks:")
        print("- Keep memory limits (set 512Mi if missing)")
        print("- Remove CPU limits")
        print("- Set memory requests to 50Mi")
        print("- Set CPU requests to 10m")
        print("- Remove empty resources blocks")
        print("- Processes both container resources AND Helm chart values")
        sys.exit(1)

    process_dir(sys.argv[1])
