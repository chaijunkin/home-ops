terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4"
    }
    random = {
      source = "hashicorp/random"
    }
    sops = {
      source  = "carlpett/sops"
      version = "1.3.0"
    }
  }
  backend "s3" {
    bucket   = "tf-state-bucket-cloudjur-com"
    key      = "cloudflare.terraform.tfstate"
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
