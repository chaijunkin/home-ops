#!/usr/bin/env python3
"""
Kubernetes Resources Management Script

This script automates:
1. IPAM generation for Cilium load balancers
2. Adding Cilium load balancer IPs to services with ingress domains
3. Adding homepage annotations based on ingress configuration
4. Enabling Gatus components based on ingress class (external/internal)
"""

import os
import sys
import yaml
import glob
import ipaddress
import argparse
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
import re

# Configuration
LOAD_BALANCER_RANGES = {
    'internal': '10.10.30.32/27',  # 10.10.30.32 - 10.10.30.63
    'external': '10.10.30.64/27',  # 10.10.30.64 - 10.10.30.95
    'gateway': '10.10.30.96/27',   # 10.10.30.96 - 10.10.30.127
}

RESERVED_IPS = {
    '10.10.30.33',  # headlamp
    '10.10.30.34',  # ingress-nginx-internal
    '10.10.30.65',  # ingress-nginx-external
    '10.10.30.70',  # k8s-gateway
}

HOMEPAGE_GROUPS = {
    'infrastructure': 'Compute/Storage Infrastructure',
    'monitoring': 'Observability',
    'media': 'Media',
    'downloads': 'Downloads',
    'security': 'Security',
    'database': 'Database',
    'home-automation': 'Home Automation',
    'network': 'Network',
    'default': 'Applications'
}

HOMEPAGE_ICONS_BASE = "https://raw.githubusercontent.com/chaijunkin/dashboard-icons/main/png"

class K8sResourceManager:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.kubernetes_dir = self.root_dir / "kubernetes"
        self.docs_dir = self.root_dir / "docs"
        self.allocated_ips = set()
        self.ingress_mappings = {}
        self.load()

    def load(self):
        """Load existing configurations and IP allocations"""
        self._load_existing_ips()
        self._scan_ingress_resources()

    def _load_existing_ips(self):
        """Load already allocated IPs from existing resources"""
        # Scan HelmRelease files for existing io.cilium/lb-ipam-ips annotations
        for helm_file in self.kubernetes_dir.rglob("helmrelease.yaml"):
            try:
                with open(helm_file, 'r') as f:
                    content = f.read()

                # Handle multiple documents in a single file
                documents = content.split('---')
                for doc_content in documents:
                    doc_content = doc_content.strip()
                    if not doc_content:
                        continue
                    try:
                        doc = yaml.safe_load(doc_content)
                        if doc and isinstance(doc, dict):
                            self._extract_ips_from_helm(doc)
                    except yaml.YAMLError:
                        # If YAML parsing fails, try to extract IPs using regex
                        self._extract_ips_with_regex(doc_content)
            except Exception as e:
                # Fallback to regex-based extraction for problematic files
                try:
                    with open(helm_file, 'r') as f:
                        content = f.read()
                        self._extract_ips_with_regex(content)
                except:
                    pass  # Skip files we can't process at all

        # Add reserved IPs
        self.allocated_ips.update(RESERVED_IPS)
        print(f"Loaded {len(self.allocated_ips)} allocated IPs")

    def _extract_ips_from_helm(self, content):
        """Extract IP addresses from HelmRelease content"""
        if not isinstance(content, dict):
            return

        # Get the HelmRelease name for tracking
        helm_name = content.get('metadata', {}).get('name', 'unknown')

        def search_for_ips(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == 'io.cilium/lb-ipam-ips' and isinstance(value, str):
                        # Handle both single IPs and comma-separated lists
                        ips = [ip.strip() for ip in value.split(',')]
                        for ip in ips:
                            try:
                                ipaddress.ip_address(ip)
                                self.allocated_ips.add(ip)
                                # Store the mapping of IP to service name
                                if not hasattr(self, 'ip_to_service'):
                                    self.ip_to_service = {}
                                self.ip_to_service[ip] = helm_name
                            except ValueError:
                                pass
                    elif isinstance(value, (dict, list)):
                        search_for_ips(value)
            elif isinstance(obj, list):
                for item in obj:
                    search_for_ips(item)

        search_for_ips(content)

    def _extract_ips_with_regex(self, content: str):
        """Extract IP addresses using regex as fallback when YAML parsing fails"""
        import re

        # Look for Cilium LB IP annotations
        pattern = r'io\.cilium/lb-ipam-ips["\']?\s*:\s*["\']?([0-9.,\s]+)["\']?'
        matches = re.findall(pattern, content)

        for match in matches:
            # Handle comma-separated IPs
            ips = [ip.strip() for ip in match.split(',')]
            for ip in ips:
                try:
                    ipaddress.ip_address(ip)
                    self.allocated_ips.add(ip)
                except ValueError:
                    pass

        # Also look for direct IP patterns in service annotations
        ip_pattern = r'10\.10\.30\.\d+'
        ip_matches = re.findall(ip_pattern, content)
        for ip in ip_matches:
            if 'io.cilium/lb-ipam-ips' in content:
                try:
                    ipaddress.ip_address(ip)
                    self.allocated_ips.add(ip)
                except ValueError:
                    pass

    def _get_service_name_from_path(self, file_path: str) -> str:
        """Extract service name from file path"""
        path_parts = str(file_path).split('/')

        # Look for the pattern: .../apps/namespace/service-name/app/helmrelease.yaml
        if 'apps' in path_parts:
            apps_index = path_parts.index('apps')
            if len(path_parts) > apps_index + 2:
                return path_parts[apps_index + 2]  # service-name

        # Fallback: try to get from the directory name before 'app'
        if 'app' in path_parts:
            app_index = path_parts.index('app')
            if app_index > 0:
                return path_parts[app_index - 1]

        # Last resort: get the parent directory name
        if len(path_parts) >= 2:
            return path_parts[-2]

        return 'unknown'

    def _scan_ingress_resources(self):
        """Scan for ingress resources to understand the current setup"""
        for yaml_file in self.kubernetes_dir.rglob("*.yaml"):
            if 'test' in str(yaml_file) or 'archive' in str(yaml_file):
                continue

            try:
                with open(yaml_file, 'r') as f:
                    content = f.read()

                # Handle multiple YAML documents
                documents = content.split('---')
                for doc_content in documents:
                    doc_content = doc_content.strip()
                    if not doc_content:
                        continue
                    try:
                        doc = yaml.safe_load(doc_content)
                        if doc and isinstance(doc, dict):
                            self._process_yaml_doc(doc, yaml_file)
                    except yaml.YAMLError:
                        # Skip documents that can't be parsed
                        continue
            except Exception:
                # Skip files we can't read at all
                continue

    def _process_yaml_doc(self, doc, file_path):
        """Process individual YAML documents"""
        kind = doc.get('kind', '')

        if kind == 'HelmRelease':
            self._process_helm_release(doc, file_path)
        elif kind == 'Ingress':
            self._process_ingress(doc, file_path)

    def _process_helm_release(self, doc, file_path):
        """Process HelmRelease for ingress configurations"""
        metadata = doc.get('metadata', {})
        app_name = metadata.get('name', '')
        namespace = file_path.parts[-4] if len(file_path.parts) >= 4 else 'default'

        values = doc.get('spec', {}).get('values', {})

        # Check for ingress configurations
        ingresses = values.get('ingress', {})
        if not isinstance(ingresses, dict):
            return

        for ingress_name, ingress_config in ingresses.items():
            if not isinstance(ingress_config, dict) or not ingress_config.get('enabled', False):
                continue

            class_name = ingress_config.get('className', 'internal')
            hosts = ingress_config.get('hosts', [])

            if hosts:
                for host_config in hosts:
                    if isinstance(host_config, dict):
                        host = host_config.get('host', '')
                        if host and '${SECRET_DOMAIN}' in host:
                            self.ingress_mappings[app_name] = {
                                'namespace': namespace,
                                'class': class_name,
                                'host': host,
                                'file_path': str(file_path),
                                'ingress_name': ingress_name
                            }
                            break

    def _process_ingress(self, doc, file_path):
        """Process standalone Ingress resources"""
        metadata = doc.get('metadata', {})
        app_name = metadata.get('name', '')
        namespace = metadata.get('namespace', 'default')

        spec = doc.get('spec', {})
        class_name = spec.get('ingressClassName', 'internal')

        rules = spec.get('rules', [])
        if rules and isinstance(rules[0], dict):
            host = rules[0].get('host', '')
            if host and '${SECRET_DOMAIN}' in host:
                self.ingress_mappings[app_name] = {
                    'namespace': namespace,
                    'class': class_name,
                    'host': host,
                    'file_path': str(file_path),
                    'ingress_name': 'main'
                }

    def get_next_available_ip(self, range_type: str) -> str:
        """Get the next available IP from the specified range"""
        if range_type not in LOAD_BALANCER_RANGES:
            raise ValueError(f"Unknown range type: {range_type}")

        network = ipaddress.ip_network(LOAD_BALANCER_RANGES[range_type])

        for ip in network.hosts():
            ip_str = str(ip)
            if ip_str not in self.allocated_ips:
                self.allocated_ips.add(ip_str)
                return ip_str

        raise RuntimeError(f"No available IPs in {range_type} range")

    def generate_ipam_documentation(self):
        """Generate IPAM documentation"""
        doc_content = """# Cilium Load Balancer IPAM

## IP Address Allocation

### Ranges
"""

        for range_name, cidr in LOAD_BALANCER_RANGES.items():
            network = ipaddress.ip_network(cidr)
            doc_content += f"- **{range_name.title()}**: `{cidr}` ({network.network_address} - {network.broadcast_address})\n"

        doc_content += f"""
### Reserved/Allocated IPs
"""

        # Sort allocated IPs
        sorted_ips = sorted(self.allocated_ips, key=ipaddress.ip_address)

        for ip in sorted_ips:
            # Try to find what service uses this IP
            service = self._find_service_by_ip(ip)
            doc_content += f"- `{ip}` - {service}\n"

        # Write documentation
        ipam_doc_file = self.docs_dir / "cilium-ipam.md"
        with open(ipam_doc_file, 'w') as f:
            f.write(doc_content)

        print(f"Generated IPAM documentation: {ipam_doc_file}")

    def dry_run_analysis(self):
        """Show what changes would be made without actually making them"""
        print("📊 Current IPAM Status:")
        print(f"   - Internal range: {LOAD_BALANCER_RANGES['internal']}")
        print(f"   - External range: {LOAD_BALANCER_RANGES['external']}")
        print(f"   - Gateway range: {LOAD_BALANCER_RANGES['gateway']}")
        print(f"   - Total allocated IPs: {len(self.allocated_ips)}")

        print("\n🔍 Services with ingress configurations:")
        services_needing_lb = []
        services_with_lb = []

        for app_name, config in self.ingress_mappings.items():
            class_name = config['class']
            file_path = config['file_path']
            host = config.get('host', 'N/A')

            # Check if already has LB IP
            try:
                with open(file_path, 'r') as f:
                    content = f.read()

                if 'io.cilium/lb-ipam-ips' in content:
                    # Extract existing IP
                    import re
                    ip_match = re.search(r'io\.cilium/lb-ipam-ips:\s*["\']?([0-9.]+)["\']?', content)
                    existing_ip = ip_match.group(1) if ip_match else 'unknown'
                    services_with_lb.append({
                        'name': app_name,
                        'class': class_name,
                        'host': host,
                        'ip': existing_ip
                    })
                else:
                    range_type = 'external' if class_name == 'external' else 'internal'
                    services_needing_lb.append({
                        'name': app_name,
                        'class': class_name,
                        'host': host,
                        'range': range_type
                    })
            except Exception as e:
                print(f"   ⚠️  Error analyzing {app_name}: {e}")

        if services_with_lb:
            print(f"\n✅ Services already with load balancer IPs ({len(services_with_lb)}):")
            for svc in services_with_lb:
                print(f"   - {svc['name']} ({svc['class']}) -> {svc['ip']} | {svc['host']}")

        if services_needing_lb:
            print(f"\n🚀 Services that would get load balancer IPs ({len(services_needing_lb)}):")
            temp_allocated = self.allocated_ips.copy()
            for svc in services_needing_lb:
                try:
                    # Get what IP would be assigned
                    next_ip = self._get_next_ip_for_range(svc['range'], temp_allocated)
                    temp_allocated.add(next_ip)  # Add to temp set to avoid duplicates
                    print(f"   - {svc['name']} ({svc['class']}) -> {next_ip} | {svc['host']}")
                except Exception as e:
                    print(f"   - {svc['name']} ({svc['class']}) -> ERROR: {e}")
        else:
            print("\n✅ No services need load balancer IPs")

        print("\n📋 Summary:")
        print(f"   - Services with LB IPs: {len(services_with_lb)}")
        print(f"   - Services needing LB IPs: {len(services_needing_lb)}")
        print(f"   - Total services with ingress: {len(self.ingress_mappings)}")

    def _get_next_ip_for_range(self, range_type: str, allocated_set: Set[str]) -> str:
        """Get next available IP without modifying the main allocated_ips set"""
        if range_type not in LOAD_BALANCER_RANGES:
            raise ValueError(f"Unknown range type: {range_type}")

        network = ipaddress.ip_network(LOAD_BALANCER_RANGES[range_type])

        for ip in network.hosts():
            ip_str = str(ip)
            if ip_str not in allocated_set:
                return ip_str

        raise RuntimeError(f"No available IPs in {range_type} range")

    def _find_service_by_ip(self, ip: str) -> str:
        """Find which service uses the given IP"""
        if ip in RESERVED_IPS:
            known_services = {
                '10.10.30.33': 'headlamp',
                '10.10.30.34': 'ingress-nginx-internal',
                '10.10.30.65': 'ingress-nginx-external',
                '10.10.30.70': 'k8s-gateway'
            }
            return known_services.get(ip, 'Reserved')

        # Use the stored IP to service mapping if available
        if hasattr(self, 'ip_to_service') and ip in self.ip_to_service:
            return self.ip_to_service[ip]

        # Search through all HelmRelease files for this IP
        for helm_file in self.kubernetes_dir.rglob("helmrelease.yaml"):
            try:
                with open(helm_file, 'r') as f:
                    content = f.read()
                    if ip in content and 'io.cilium/lb-ipam-ips' in content:
                        # Try to extract the HelmRelease name from YAML
                        try:
                            # Handle multiple documents
                            documents = content.split('---')
                            for doc_content in documents:
                                doc_content = doc_content.strip()
                                if not doc_content or ip not in doc_content:
                                    continue
                                try:
                                    yaml_content = yaml.safe_load(doc_content)
                                    if yaml_content and isinstance(yaml_content, dict):
                                        metadata = yaml_content.get('metadata', {})
                                        name = metadata.get('name', 'unknown')
                                        if name != 'unknown':
                                            return name
                                except yaml.YAMLError:
                                    continue
                        except:
                            pass

                        # Fallback to path-based name extraction
                        return self._get_service_name_from_path(helm_file)
            except Exception as e:
                continue

        # Search through ingress mappings as fallback
        for app_name, config in self.ingress_mappings.items():
            if self._app_uses_ip(config['file_path'], ip):
                return app_name

        return 'app'

    def _app_uses_ip(self, file_path: str, ip: str) -> bool:
        """Check if an app uses the given IP"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                return ip in content
        except:
            return False

    def add_load_balancer_ips(self):
        """Add Cilium load balancer IPs to services with ingress domains"""
        modified_files = []

        for app_name, config in self.ingress_mappings.items():
            class_name = config['class']
            file_path = config['file_path']

            # Determine IP range based on ingress class
            if class_name == 'external':
                range_type = 'external'
            elif class_name == 'internal':
                range_type = 'internal'
            else:
                continue

            # Check if IP is already assigned
            try:
                with open(file_path, 'r') as f:
                    content = f.read()

                if 'io.cilium/lb-ipam-ips' in content:
                    print(f"Skipping {app_name}: already has load balancer IP")
                    continue

                # Get next available IP
                ip = self.get_next_available_ip(range_type)

                # Add IP to service annotations
                updated_content = self._add_lb_ip_to_helm(content, ip)

                if updated_content != content:
                    with open(file_path, 'w') as f:
                        f.write(updated_content)
                    modified_files.append(file_path)
                    print(f"Added IP {ip} to {app_name} ({class_name})")

            except Exception as e:
                print(f"Error processing {app_name}: {e}")

        return modified_files

    def _add_lb_ip_to_helm(self, content: str, ip: str) -> str:
        """Add load balancer IP annotation to HelmRelease"""
        lines = content.split('\n')
        modified_lines = []
        in_service_section = False
        in_annotations_section = False
        indent_level = 0

        i = 0
        while i < len(lines):
            line = lines[i]

            # Detect service section
            if 'service:' in line and not line.strip().startswith('#'):
                in_service_section = True
                indent_level = len(line) - len(line.lstrip())
                modified_lines.append(line)

                # Look ahead for annotations
                j = i + 1
                found_annotations = False
                while j < len(lines) and (not lines[j].strip() or lines[j].startswith(' ' * (indent_level + 1))):
                    if 'annotations:' in lines[j]:
                        found_annotations = True
                        break
                    j += 1

                if not found_annotations:
                    # Add annotations section
                    modified_lines.append(' ' * (indent_level + 2) + 'annotations:')
                    modified_lines.append(' ' * (indent_level + 4) + f'io.cilium/lb-ipam-ips: {ip}')

            elif in_service_section and 'annotations:' in line:
                modified_lines.append(line)
                annotation_indent = len(line) - len(line.lstrip()) + 2

                # Add our annotation right after
                modified_lines.append(' ' * annotation_indent + f'io.cilium/lb-ipam-ips: {ip}')
                in_service_section = False

            else:
                modified_lines.append(line)

                # Reset service section tracking
                if in_service_section and line.strip() and len(line) - len(line.lstrip()) <= indent_level:
                    in_service_section = False

            i += 1

        return '\n'.join(modified_lines)

    def add_homepage_annotations(self):
        """Add homepage annotations to ingress resources"""
        modified_files = []

        for app_name, config in self.ingress_mappings.items():
            file_path = config['file_path']
            namespace = config['namespace']

            try:
                with open(file_path, 'r') as f:
                    content = f.read()

                if 'gethomepage.dev/enabled' in content:
                    print(f"Skipping {app_name}: already has homepage annotations")
                    continue

                # Generate homepage annotations
                annotations = self._generate_homepage_annotations(app_name, namespace)

                # Add annotations to ingress
                updated_content = self._add_homepage_annotations_to_helm(content, annotations)

                if updated_content != content:
                    with open(file_path, 'w') as f:
                        f.write(updated_content)
                    modified_files.append(file_path)
                    print(f"Added homepage annotations to {app_name}")

            except Exception as e:
                print(f"Error processing {app_name}: {e}")

        return modified_files

    def _generate_homepage_annotations(self, app_name: str, namespace: str) -> Dict[str, str]:
        """Generate homepage annotations for an app"""
        # Determine group based on namespace
        group = HOMEPAGE_GROUPS.get(namespace, HOMEPAGE_GROUPS['default'])

        # Generate description
        description = self._generate_description(app_name)

        # Generate icon URL
        icon_url = f"{HOMEPAGE_ICONS_BASE}/{app_name.lower()}.png"

        annotations = {
            'gethomepage.dev/enabled': '"true"',
            'gethomepage.dev/group': group,
            'gethomepage.dev/name': app_name.title(),
            'gethomepage.dev/description': description,
            'gethomepage.dev/icon': icon_url
        }

        # Add widget configuration for known apps
        widget_config = self._get_widget_config(app_name)
        if widget_config:
            annotations.update(widget_config)

        return annotations

    def _generate_description(self, app_name: str) -> str:
        """Generate description for an app"""
        descriptions = {
            'jellyseerr': 'Media Request Management',
            'grafana': 'Monitoring Dashboard',
            'headlamp': 'Kubernetes Dashboard',
            'plex': 'Media Server',
            'sonarr': 'Series Management',
            'radarr': 'Movie Management',
            'bazarr': 'Subtitle Management',
            'prowlarr': 'Indexer Management',
            'transmission': 'BitTorrent Client',
            'gatus': 'Status Page',
            'authentik': 'Authentication Provider',
            'vaultwarden': 'Password Manager',
            'paperless': 'Document Management',
            'home-assistant': 'Home Automation',
            'zigbee2mqtt': 'Zigbee Bridge'
        }

        return descriptions.get(app_name.lower(), f"{app_name.title()} Service")

    def _get_widget_config(self, app_name: str) -> Dict[str, str]:
        """Get widget configuration for known apps"""
        widgets = {
            'jellyseerr': {
                'gethomepage.dev/widget.type': 'overseerr',
                'gethomepage.dev/widget.url': f'http://{app_name}.media:5055',
                'gethomepage.dev/widget.key': '{{ `{{HOMEPAGE_VAR_OVERSEERR_TOKEN}}` }}'
            },
            'grafana': {
                'gethomepage.dev/widget.type': 'grafana',
                'gethomepage.dev/widget.url': f'http://{app_name}.observability:3000',
                'gethomepage.dev/widget.username': '{{ `{{HOMEPAGE_VAR_GRAFANA_USERNAME}}` }}',
                'gethomepage.dev/widget.password': '{{ `{{HOMEPAGE_VAR_GRAFANA_PASSWORD}}` }}'
            },
            'sonarr': {
                'gethomepage.dev/widget.type': 'sonarr',
                'gethomepage.dev/widget.url': f'http://{app_name}.downloads:8989',
                'gethomepage.dev/widget.key': '{{ `{{HOMEPAGE_VAR_SONARR_TOKEN}}` }}'
            },
            'radarr': {
                'gethomepage.dev/widget.type': 'radarr',
                'gethomepage.dev/widget.url': f'http://{app_name}.downloads:7878',
                'gethomepage.dev/widget.key': '{{ `{{HOMEPAGE_VAR_RADARR_TOKEN}}` }}'
            }
        }

        return widgets.get(app_name.lower(), {})

    def _add_homepage_annotations_to_helm(self, content: str, annotations: Dict[str, str]) -> str:
        """Add homepage annotations to HelmRelease ingress section"""
        lines = content.split('\n')
        modified_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # Look for ingress annotations section
            if 'ingress:' in line and not line.strip().startswith('#'):
                modified_lines.append(line)

                # Look for annotations in this ingress section
                j = i + 1
                ingress_indent = len(line) - len(line.lstrip())

                while j < len(lines):
                    current_line = lines[j]

                    if current_line.strip() and len(current_line) - len(current_line.lstrip()) <= ingress_indent:
                        break

                    if 'annotations:' in current_line:
                        modified_lines.append(current_line)
                        annotation_indent = len(current_line) - len(current_line.lstrip()) + 2

                        # Add homepage annotations
                        for key, value in annotations.items():
                            modified_lines.append(' ' * annotation_indent + f'{key}: {value}')

                        # Skip to next line and continue
                        i = j
                        break

                    j += 1
                else:
                    # No annotations found, continue normally
                    pass
            else:
                modified_lines.append(line)

            i += 1

        return '\n'.join(modified_lines)

    def enable_gatus_components(self):
        """Enable Gatus components based on ingress class - DISABLED"""
        print("Gatus components functionality is disabled - not touching components/gatus directory")
        return

    def _create_gatus_components(self, services: List[str], component_type: str):
        """Create Gatus component configuration - DISABLED"""
        print("Gatus component creation is disabled")
        return

    def _generate_gatus_config(self, services: List[str], component_type: str) -> str:
        """Generate Gatus configuration for services - DISABLED"""
        return "# Gatus configuration generation is disabled"


def main():
    parser = argparse.ArgumentParser(description='Manage Kubernetes resources for home-ops')
    parser.add_argument('--root-dir', default='.', help='Root directory of the project')
    parser.add_argument('--generate-ipam-docs', action='store_true', help='Generate IPAM documentation')
    parser.add_argument('--add-load-balancer-ips', action='store_true', help='Add Cilium load balancer IPs')
    parser.add_argument('--add-homepage-annotations', action='store_true', help='Add homepage annotations')
    # parser.add_argument('--enable-gatus', action='store_true', help='Enable Gatus components')  # DISABLED
    parser.add_argument('--all', action='store_true', help='Run all operations (except Gatus)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')

    args = parser.parse_args()

    if not any([args.generate_ipam_docs, args.add_load_balancer_ips, args.add_homepage_annotations, args.all, args.dry_run]):
        parser.print_help()
        return

    manager = K8sResourceManager(args.root_dir)

    if args.dry_run:
        print("DRY RUN MODE - No changes will be made")
        print("="*50)
        manager.dry_run_analysis()
        return

    if args.all or args.generate_ipam_docs:
        print("Generating IPAM documentation...")
        manager.generate_ipam_documentation()

    if args.all or args.add_load_balancer_ips:
        print("Adding load balancer IPs...")
        modified_files = manager.add_load_balancer_ips()
        print(f"Modified {len(modified_files)} files")

    if args.all or args.add_homepage_annotations:
        print("Adding homepage annotations...")
        modified_files = manager.add_homepage_annotations()
        print(f"Modified {len(modified_files)} files")

    # Gatus functionality disabled
    # if args.all or args.enable_gatus:
    #     print("Enabling Gatus components...")
    #     manager.enable_gatus_components()

    print("Done!")


if __name__ == '__main__':
    main()
