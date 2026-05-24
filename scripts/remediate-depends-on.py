#!/usr/bin/env python3
import os
import sys
from ruamel.yaml import YAML

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

APPS_DIR = "kubernetes/apps"
ES_STORE_DEP = {"name": "external-secrets-stores", "namespace": "external-secrets"}
VOLSYNC_DEP = {"name": "volsync", "namespace": "volsync-system"}
PG_CLUSTER_DEP = {"name": "cloudnative-pg-cluster", "namespace": "database"}
DRAGONFLY_DEP = {"name": "dragonfly-cluster", "namespace": "database"}
AUTHENTIK_DEP = {"name": "authentik", "namespace": "security"}
MULTUS_DEP = {"name": "multus-config", "namespace": "network"}
OPENEBS_DEP = {"name": "openebs", "namespace": "storage"}
LOCAL_HOSTPATH_DEP = {"name": "local-hostpath", "namespace": "storage"}


def get_abs_path(rel_path):
    # Flux paths are usually relative to repo root
    clean_path = rel_path[2:] if rel_path.startswith("./") else rel_path
    return os.path.join(os.getcwd(), clean_path)

def has_content(path, pattern):
    if not os.path.exists(path):
        return False
    for root, dirs, files in os.walk(path):
        for f in files:
            if f.endswith(".yaml"):
                try:
                    with open(os.path.join(root, f), "r") as file:
                        if pattern in file.read():
                            return True
                except:
                    pass
    return False

def add_dependency(spec, dep):
    if "dependsOn" not in spec:
        spec["dependsOn"] = []
    
    # Check if already present
    for existing in spec["dependsOn"]:
        if existing.get("name") == dep["name"] and existing.get("namespace") == dep.get("namespace"):
            return False
            
    spec["dependsOn"].append(dep)
    # Sort dependsOn by name
    spec["dependsOn"] = sorted(spec["dependsOn"], key=lambda x: x.get("name", ""))
    return True

def remove_dependency(spec, dep_name):
    if "dependsOn" not in spec:
        return False
    
    initial_len = len(spec["dependsOn"])
    spec["dependsOn"] = [d for d in spec["dependsOn"] if d.get("name") != dep_name]
    
    if len(spec["dependsOn"]) == 0:
        del spec["dependsOn"]
        return True
        
    return len(spec["dependsOn"]) != initial_len

INCLUDE_OPTIONAL = False # Set to True to include non-storage dependencies

def process_ks(file_path):
    changed = False
    try:
        with open(file_path, "r") as f:
            content = f.read()
            docs = list(yaml.load_all(content))
        
        for doc in docs:
            if not doc or doc.get("kind") != "Kustomization":
                continue
            
            spec = doc.get("spec", {})
            path = spec.get("path")
            if not path:
                continue
            
            abs_path = get_abs_path(path)
            
            # --- MANDATORY: Storage ---
            # Rule: OpenEBS -> openebs
            if has_content(abs_path, "openebs"):
                if doc['metadata']['name'] != "openebs":
                    if add_dependency(spec, OPENEBS_DEP):
                        print(f"[{file_path}] Added openebs dependency to {doc['metadata']['name']}")
                        changed = True

            # Rule: Local Hostpath -> local-hostpath
            if has_content(abs_path, "local-hostpath"):
                if doc['metadata']['name'] != "local-hostpath":
                    if add_dependency(spec, LOCAL_HOSTPATH_DEP):
                        print(f"[{file_path}] Added local-hostpath dependency to {doc['metadata']['name']}")
                        changed = True

            # Rule: Volsync component -> openebs (MANDATORY per user request)
            components = spec.get("components", [])
            has_volsync_comp = any("volsync" in c for c in components)
            if has_volsync_comp:
                if doc['metadata']['name'] != "openebs":
                    if add_dependency(spec, OPENEBS_DEP):
                        print(f"[{file_path}] Added openebs (via volsync component) dependency to {doc['metadata']['name']}")
                        changed = True

            # --- EXCLUSIONS ---
            # Rule: Exclude NFS per user request
            if remove_dependency(spec, "csi-driver-nfs"):
                print(f"[{file_path}] Removed csi-driver-nfs dependency from {doc['metadata']['name']}")
                changed = True

            # Rule: Exclude self-dependencies
            if doc['metadata']['name'] == "openebs":
                if remove_dependency(spec, "openebs"):
                    print(f"[{file_path}] Removed self-dependency from openebs")
                    changed = True
            
            if doc['metadata']['name'] == "local-hostpath":
                if remove_dependency(spec, "local-hostpath"):
                    print(f"[{file_path}] Removed self-dependency from local-hostpath")
                    changed = True

            # --- OPTIONAL: Others ---
            if INCLUDE_OPTIONAL:
                # Rule: ExternalSecret -> external-secrets-stores
                if has_content(abs_path, "kind: ExternalSecret"):
                    if add_dependency(spec, ES_STORE_DEP):
                        print(f"[{file_path}] Added external-secrets-stores dependency to {doc['metadata']['name']}")
                        changed = True
                
                # Rule: Postgres -> cloudnative-pg-cluster
                if has_content(abs_path, "INIT_POSTGRES_HOST") or has_content(abs_path, "POSTGRES_HOST"):
                    if add_dependency(spec, PG_CLUSTER_DEP):
                        print(f"[{file_path}] Added cloudnative-pg-cluster dependency to {doc['metadata']['name']}")
                        changed = True

                # Rule: Dragonfly/Redis -> dragonfly-cluster
                if has_content(abs_path, "dragonfly.database"):
                    if add_dependency(spec, DRAGONFLY_DEP):
                        print(f"[{file_path}] Added dragonfly-cluster dependency to {doc['metadata']['name']}")
                        changed = True

                # Rule: Volsync component -> volsync (Operator)
                if has_volsync_comp:
                    if add_dependency(spec, VOLSYNC_DEP):
                        print(f"[{file_path}] Added volsync operator dependency to {doc['metadata']['name']}")
                        changed = True

                # Rule: Authentik (SSO) -> authentik
                if has_content(abs_path, "authentik"):
                     if doc['metadata']['name'] != "authentik":
                        if add_dependency(spec, AUTHENTIK_DEP):
                            print(f"[{file_path}] Added authentik dependency to {doc['metadata']['name']}")
                            changed = True

                # Rule: Multus -> multus-config
                if has_content(abs_path, "k8s.v1.cni.cncf.io/networks"):
                    if add_dependency(spec, MULTUS_DEP):
                        print(f"[{file_path}] Added multus-config dependency to {doc['metadata']['name']}")
                        changed = True

        if changed:
            with open(file_path, "w") as f:
                yaml.dump_all(docs, f)
                
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

def main():
    for root, dirs, files in os.walk(APPS_DIR):
        if "ks.yaml" in files:
            process_ks(os.path.join(root, "ks.yaml"))

if __name__ == "__main__":
    main()
