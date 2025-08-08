#!/usr/bin/env python3
"""Test script to verify service annotation functionality"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

def test_service_annotation():
    # Import the class
    from manage_k8s_resources import K8sResourceManager

    # Create a test YAML content similar to cyberchef
    test_content = """apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: test-app
spec:
  values:
    service:
      main:
        ports:
          http:
            port: 8000
    ingress:
      main:
        enabled: true
        ingressClassName: internal"""

    # Create manager and test the annotation adding
    manager = K8sResourceManager()
    result = manager._add_lb_ip_to_helm(test_content, '10.10.30.50')

    print('Original:')
    print(test_content)
    print('\n' + '='*50)
    print('After adding annotation:')
    print(result)
    print('\n' + '='*50)

    # Check if annotation was added
    has_annotation = 'io.cilium/lb-ipam-ips: 10.10.30.50' in result
    has_annotations_section = 'annotations:' in result

    print(f"Has annotations section: {has_annotations_section}")
    print(f"Has Cilium IP annotation: {has_annotation}")
    print(f"Test result: {'PASSED' if has_annotation and has_annotations_section else 'FAILED'}")

    return has_annotation and has_annotations_section

if __name__ == "__main__":
    test_service_annotation()
