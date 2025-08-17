#!/usr/bin/env python3
import os
import sys
import re
from ruamel.yaml import YAML

def comment_block(lines, start_idx, end_idx):
    # Only comment lines that are part of the ingress block (by indentation)
    if start_idx is None or end_idx is None:
        return lines
    base_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
    for i in range(start_idx, end_idx):
        l = lines[i]
        # Always comment the ingress: line if not already commented
        if i == start_idx:
            if not l.lstrip().startswith('#'):
                lines[i] = '# ' + l
            continue
        # Skip blank lines
        if l.strip() == '':
            continue
        # Only comment lines that are not already commented and are part of the block
        curr_indent = len(l) - len(l.lstrip())
        if curr_indent > base_indent and not l.lstrip().startswith('#'):
            lines[i] = '# ' + l
    return lines

def extract_block(lines, key):
    start = None
    end = None
    key_regex = re.compile(rf'^(?P<indent>\s*){key}:')
    for idx, line in enumerate(lines):
        m = key_regex.match(line)
        if m:
            start = idx
            base_indent = len(m.group('indent'))
            # Find where the block ends: next line with same or less indentation (not a comment)
            for j in range(idx+1, len(lines)):
                l = lines[j]
                if l.strip() == '' or l.lstrip().startswith('#'):
                    continue
                curr_indent = len(l) - len(l.lstrip())
                if curr_indent <= base_indent:
                    end = j
                    break
            if end is None:
                end = len(lines)
            break
    return start, end

def get_service_info(doc):
    try:
        svc = doc['spec']['values']['service']['app']
        port = svc['ports']['http']['port']
        name = svc.get('controller', doc['metadata']['name'])
        if isinstance(name, dict) and 'ref' in name:
            name = name['ref']
        return name, port
    except Exception:
        return doc['metadata']['name'], 80

def build_route_block(app_name, port, parent_ref_name='internal'):
    return {
        'app': {
            'hostnames': [
                f"{app_name}.cloudjur.com"
            ],
            'parentRefs': [
                {
                    'name': parent_ref_name,
                    'namespace': 'kube-system',
                    'sectionName': 'https'
                }
            ],
            'rules': [
                {
                    'backendRefs': [
                        {
                            'port': port,
                            'name': app_name
                        }
                    ]
                }
            ]
        }
    }

def should_migrate(doc, lines):
    # Check for ingress block
    ingress_start, ingress_end = extract_block(lines, 'ingress')
    if ingress_start is None:
        return False
    # Check for route block
    values = doc.get('spec', {}).get('values', {})
    if 'route' in values:
        return False
    # Check for OCIRepository and app-template
    chart = doc.get('spec', {}).get('chartRef', {})
    if chart.get('kind') != 'OCIRepository' or chart.get('name') != 'app-template':
        return False
    return True

def migrate_helmrelease(path):
    yaml = YAML()
    yaml.preserve_quotes = True
    with open(path) as f:
        docs = list(yaml.load_all(f))
    if not docs:
        return
    doc = docs[0]
    values = doc.get('spec', {}).get('values', {})
    ingress_obj = values.get('ingress')
    if ingress_obj and isinstance(ingress_obj, dict):
        ingress_app = ingress_obj.get('app', {})
        class_name = ingress_app.get('className')
        parent_ref_name = 'external' if class_name == 'external' else 'internal'
        # Remove the ingress block directly from the YAML structure
        del values['ingress']
        app_name, port = get_service_info(doc)
        route_block = build_route_block(app_name, port, parent_ref_name)
        # Copy homepage annotations only (exclude external-dns)
        annotations = ingress_app.get('annotations', {})
        if annotations:
            homepage_keys = [k for k in annotations if k.startswith('gethomepage.dev/')]
            if homepage_keys:
                route_block['app']['annotations'] = {k: annotations[k] for k in homepage_keys}
        values['route'] = route_block
        docs[0] = doc
        with open(path, 'w') as f:
            yaml.dump_all(docs, f)
        print(f"Migrated {path}: removed ingress, added route block.")

def find_helmreleases(root):
    helmreleases = []
    for dirpath, dirnames, filenames in os.walk(root):
        for filename in filenames:
            if filename == 'helmrelease.yaml':
                helmreleases.append(os.path.join(dirpath, filename))
    return helmreleases

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: migrate_ingress_to_route.py <root_path>")
        sys.exit(1)
    root = sys.argv[1]
    files = find_helmreleases(root)
    if not files:
        print(f"No helmrelease.yaml files found in {root}")
        sys.exit(1)
    for file in files:
        migrate_helmrelease(file)