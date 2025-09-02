terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5"
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
    workspaces { name = "cloudflare-workspace" }
  }
}

provider "cloudflare" {
  # ... any other configuration
  api_token = local.cloudflare_api_token
}

provider "random" {
}

# data "sops_file" "cloudflare_secrets" {
#   source_file = "secret.sops.yaml"
# }
