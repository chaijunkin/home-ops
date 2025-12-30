terraform {
  backend "s3" {
    bucket   = "tf-state-bucket-cloudjur-com"
    key      = "terraform.tfstate"
    use_lockfile = true
    endpoints = {
      s3 = "https://8550295d25a8172e9fe4f9f7a7f327be.r2.cloudflarestorage.com"
    }

    region                      = "auto"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "3.0.1"
    }
    proxmox = {
      source  = "bpg/proxmox"
      version = "0.90.0"
    }
    talos = {
      source  = "siderolabs/talos"
      version = "0.10.0"
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

