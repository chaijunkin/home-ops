terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "2.38.0"
    }
    proxmox = {
      source  = "bpg/proxmox"
      version = "0.81.0"
    }
    talos = {
      source  = "siderolabs/talos"
      version = "0.8.1"
    }
  }
}

provider "proxmox" {
  endpoint = var.proxmox.endpoint
  insecure = var.proxmox.insecure

  # api_token = var.proxmox_api_token
  username = var.proxmox.username
  password = var.proxmox.password # you need this for proxmoxo_vm non_mapped hostpci
  ssh {
    agent = false
    # username = var.proxmox.username
    private_key = file("~/.ssh/jk_inventory") # Ensure this file exists and has the correct permissions
  }
}

provider "kubernetes" {
  host                   = module.talos.kube_config.kubernetes_client_configuration.host
  client_certificate     = base64decode(module.talos.kube_config.kubernetes_client_configuration.client_certificate)
  client_key             = base64decode(module.talos.kube_config.kubernetes_client_configuration.client_key)
  cluster_ca_certificate = base64decode(module.talos.kube_config.kubernetes_client_configuration.ca_certificate)
}

terraform {
  cloud {
    organization = "chaijunkin"
    workspaces { name = "proxmox-talos-workspace" }
  }
}
