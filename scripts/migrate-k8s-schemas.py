#!/usr/bin/env python3

import argparse
import yaml
from pathlib import Path

def get_schema_url(api_version, kind, doc=None):
    if '/' in api_version:
        group, version = api_version.split('/', 1)
    else:
        group = ''
        version = api_version

    version_raw = version
    version_num = version.lstrip('v')
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
        return f'https://kubernetes-schemas.pages.dev/helm.toolkit.fluxcd.io/helmrelease_{version_raw}.json'

    if group == 'source.toolkit.fluxcd.io' and kind == 'OCIRepository':
        return f'https://kubernetes-schemas.pages.dev/source.toolkit.fluxcd.io/ocirepository_{version_num}.json'

    if group == 'notification.toolkit.fluxcd.io':
        if kind_lower == 'alert':
            return f'https://kubernetes-schemas.pages.dev/notification.toolkit.fluxcd.io/alert_{version_raw}.json'
        if kind_lower == 'provider':
            return f'https://kubernetes-schemas.pages.dev/notification.toolkit.fluxcd.io/provider_{version_num}.json'
        if kind_lower == 'receiver':
            return f'https://kubernetes-schemas.pages.dev/notification.toolkit.fluxcd.io/receiver_{version_num}.json'
        return f'https://kubernetes-schemas.pages.dev/notification.toolkit.fluxcd.io/{kind_lower}_{version_num}.json'

    if group == 'gateway.networking.k8s.io':
        return f'https://kubernetes-schemas.pages.dev/gateway.networking.k8s.io/{kind_lower}_{version_num}.json'

    if group == 'gateway.envoyproxy.io':
        return f'https://kubernetes-schemas.pages.dev/gateway.envoyproxy.io/{kind_lower}_{version_num}.json'

    if group == 'monitoring.coreos.com':
        return f'https://kubernetes-schemas.pages.dev/monitoring.coreos.com/{kind_lower}_{version_num}.json'

    if group == 'external-secrets.io':
        return f'https://kubernetes-schemas.pages.dev/external-secrets.io/externalsecret_{version_num}.json'

    if group == 'toolhive.stacklok.dev':
        return f'https://kube-schemas.pages.dev/toolhive.stacklok.dev/{kind_lower}_{version_num}.json'

    if group == 'volsync.backube' or group == 'tuppr.home-operations.com' or group == 'grafana.integreatly.org' or group.startswith('cilium.io') or group == 'cert-manager.io' or group == 'dragonflydb.io' or group == 'k8s.cni.cncf.io' or group == 'externaldns.k8s.io':
        return f'https://kubernetes-schemas.pages.dev/{group}/{kind_lower}_{version_num}.json'

    if group == '':
        return f'https://raw.githubusercontent.com/yannh/kubernetes-json-schema/master/master-standalone/{kind_lower}.json'

    return f'https://crd.cloudjur.com/{group}/{kind_lower}_{version_num}.json'

def add_schema_to_file(file_path, override=False):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.splitlines()
        existing_schema_index = next(
            (idx for idx, line in enumerate(lines) if line.strip().startswith('# yaml-language-server: $schema=')),
            None,
        )

        # Parse YAML to get apiVersion and kind
        try:
            docs = list(yaml.safe_load_all(content))
            if not docs:
                return
            doc = docs[0]  # First document
            if not isinstance(doc, dict):
                return
            api_version = doc.get('apiVersion')
            kind = doc.get('kind')
            if not api_version or not kind:
                return
        except yaml.YAMLError:
            return

        schema_url = get_schema_url(api_version, kind, doc)

        if existing_schema_index is not None:
            if override:
                lines[existing_schema_index] = f'# yaml-language-server: $schema={schema_url}'
                new_content = '\n'.join(lines) + '\n'
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Overrode schema in {file_path}")
            else:
                print(f"Schema already present in {file_path}")
            return

        # Add the schema comment
        lines = content.splitlines()
        if lines and lines[0].strip() == '---':
            # Insert after ---
            lines.insert(1, f'# yaml-language-server: $schema={schema_url}')
        else:
            # Insert at beginning
            lines.insert(0, f'# yaml-language-server: $schema={schema_url}')
            if lines and lines[1].strip() != '---':
                lines.insert(1, '---')

        new_content = '\n'.join(lines) + '\n'

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"Added schema to {file_path}")

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