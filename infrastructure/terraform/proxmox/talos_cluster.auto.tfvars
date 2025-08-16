talos_cluster_config = {
  name = "talos"
  # Only use a VIP if the nodes share a layer 2 network
  # Ref: https://www.talos.dev/v1.9/talos-guides/network/vip/#requirements
  vip     = "10.10.30.30"
  gateway = "10.10.30.1"
  # The version of talos features to use in generated machine configuration. Generally the same as image version.
  # See https://github.com/siderolabs/terraform-provider-talos/blob/main/docs/data-sources/machine_configuration.md
  # Uncomment to use this instead of version from talos_image.
  # talos_machine_config_version = "v1.9.2"
  proxmox_cluster    = "main"
  kubernetes_version = "v1.33.3" # renovate: github-releases=kubernetes/kubernetes
  cilium = {
    bootstrap_manifest_path = "talos/inline-manifests/cilium-install.yaml"
    values_file_path        = "../../../kubernetes/apps/kube-system/cilium/app/helm/values.yaml"
  }
  gateway_api_version = "v1.3.0" # renovate: github-releases=kubernetes-sigs/gateway-api
  extra_manifests     = []
  kubelet             = <<-EOT
  EOT
  api_server          = <<-EOT
    admissionControl: []
  EOT
}
