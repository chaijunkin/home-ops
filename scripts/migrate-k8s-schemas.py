#!/usr/bin/env python3

import argparse
import json
import urllib.request
import urllib.error
from ruamel.yaml import YAML
from pathlib import Path

SCHEMA_REPO_TREE_URL = 'https://api.github.com/repos/yannh/kubernetes-json-schema/git/trees/master?recursive=1'
SCHEMA_RAW_BASE_URL = 'https://raw.githubusercontent.com/yannh/kubernetes-json-schema/master'
_schema_index_cache = None


def fetch_upstream_schema_index(timeout=10):
    global _schema_index_cache
    if _schema_index_cache is not None:
        return _schema_index_cache

    schema_index = {
        'groupless': {},
        'grouped': {},
    }

    try:
        request = urllib.request.Request(SCHEMA_REPO_TREE_URL, headers={'User-Agent': 'python-urllib/3'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)

        for entry in payload.get('tree', []):
            path = entry.get('path', '')
            if not path.endswith('.json'):
                continue
            if not (path.startswith('master/') or path.startswith('master-standalone/')):
                continue

            basename = path.rsplit('/', 1)[-1]
            name = basename[:-5]
            parts = name.split('-')

            if len(parts) == 1:
                schema_index['groupless'][name] = path
                continue

            version = parts[-1]
            if not version.startswith('v'):
                schema_index['groupless'][name] = path
                continue

            if len(parts) >= 3:
                group_prefix = parts[-2]
                kind_name = '-'.join(parts[:-2])
                schema_index['grouped'][(kind_name, group_prefix, version)] = path
            else:
                schema_index['groupless'][name] = path

    except Exception as e:
        print(f'Warning: failed to fetch upstream schema index: {e}')
        schema_index = {'groupless': {}, 'grouped': {}}

    _schema_index_cache = schema_index
    return schema_index


def get_yannh_schema_url(api_version, kind):
    if not api_version or not kind:
        return None

    if '/' in api_version:
        group, version = api_version.split('/', 1)
    else:
        group = ''
        version = api_version

    version_raw = version.lstrip('v')
    version_token = version if version.startswith('v') else f'v{version_raw}'
    kind_lower = kind.lower()
    schema_index = fetch_upstream_schema_index()

    if group == '':
        path = schema_index['groupless'].get(kind_lower)
        if path:
            return f'{SCHEMA_RAW_BASE_URL}/{path}'
        return None

    group_prefix = group.split('.', 1)[0]
    path = schema_index['grouped'].get((kind_lower, group_prefix, version_token))
    if path:
        return f'{SCHEMA_RAW_BASE_URL}/{path}'

    return None


def get_schema_url(api_version, kind, doc=None):
    schema_url = get_yannh_schema_url(api_version, kind)
    if schema_url:
        return schema_url
    if '/' in api_version:
        group, version = api_version.split('/', 1)
    else:
        group = ''
        version = api_version

    version_raw = version
    version_raw = version.lstrip('v')
    kind_lower = kind.lower()

    # Known scalar schema URLs for common Kubernetes tooling resources.
    if group == 'kustomize.toolkit.fluxcd.io' and kind == 'Kustomization':
        return 'https://crd.cloudjur.com/kustomize.toolkit.fluxcd.io/kustomization_v1.json'

    if group == 'kustomize.config.k8s.io':
        return 'https://json.schemastore.org/kustomization'

    if group == 'helm.toolkit.fluxcd.io' and kind == 'HelmRelease':
        if isinstance(doc, dict):
            chart_ref = doc.get('spec', {}).get('chartRef')
            if isinstance(chart_ref, dict) and chart_ref.get('name') == 'app-template':
                return 'https://raw.githubusercontent.com/bjw-s-labs/helm-charts/app-template-5.0.0/charts/other/app-template/schemas/helmrelease-helm-v2.schema.json'

    if group == '':
        return f'https://raw.githubusercontent.com/yannh/kubernetes-json-schema/master/master-standalone/{kind_lower}.json'

    return f'https://crd.cloudjur.com/{group}/{kind_lower}_v{version_raw}.json'

def add_schema_to_file(file_path, override=False):
    try:
        yaml = YAML()
        with open(file_path, 'r', encoding='utf-8') as f:
            docs = list(yaml.load_all(f))

        if not docs:
            return

        updated = False
        for index, doc in enumerate(docs):
            if not isinstance(doc, dict):
                continue

            api_version = doc.get('apiVersion')
            kind = doc.get('kind')
            if not api_version or not kind:
                continue

            schema_url = get_schema_url(api_version, kind, doc)

            # Check if schema comment exists for this document
            comment_lines = []
            if getattr(doc, 'ca', None) and getattr(doc.ca, 'comment', None) and len(doc.ca.comment) > 0 and doc.ca.comment[0] is not None:
                comment_lines = doc.ca.comment[0]
            schema_comment = next(
                (line for line in comment_lines if line.value.strip().startswith('# yaml-language-server: $schema=')),
                None,
            )

            if schema_comment:
                if override:
                    schema_comment.value = f'# yaml-language-server: $schema={schema_url}'
                    updated = True
                # if not override, keep existing schema comment
            else:
                doc.yaml_set_start_comment(f'yaml-language-server: $schema={schema_url}')
                updated = True

        if updated:
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump_all(docs, f)
            print(f"Updated schema comments in {file_path}")

    except Exception as e:
        print(f"Error processing {file_path}: {e}")

    except Exception as e:
        print(f"Error processing {file_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Add yaml-language-server $schema comments to Kubernetes YAML files.')
    parser.add_argument('--root', type=str, default=str(Path(__file__).resolve().parents[1]),
                        help='Repository root path (default: parent of scripts/ directory).')
    parser.add_argument('--override', action='store_true',
                        help='Replace existing yaml-language-server $schema comment when present.')
    args = parser.parse_args()

    kubernetes_dir = Path(args.root) / 'kubernetes'
    if not kubernetes_dir.exists():
        print(f'Error: Kubernetes directory not found at {kubernetes_dir}')
        return

    for yaml_file in kubernetes_dir.rglob('*.yaml'):
        if yaml_file.is_file():
            add_schema_to_file(yaml_file, args.override)

    for yml_file in kubernetes_dir.rglob('*.yml'):
        if yml_file.is_file():
            add_schema_to_file(yml_file, args.override)

if __name__ == '__main__':
    main()