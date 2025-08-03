terraform {
  required_providers {
    ukumawapi = {
      source  = "pete-leese/ukumawapi"
      version = "0.4.5"
    }
    random = {
      source = "hashicorp/random"
    }
    sops = {
      source  = "carlpett/sops"
      version = "1.2.1"
    }
  }
  cloud {
    organization = "chaijunkin"
    workspaces { name = "uptimekuma-workspace" }
  }
}

provider "ukumawapi" {
  # Configuration options
  server_url              = ""
  o_auth2_password_bearer = ""
}

# data "sops_file" "cloudflare_secrets" {
#   source_file = "secret.sops.yaml"
# }
