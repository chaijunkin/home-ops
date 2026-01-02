terraform {
  required_providers {
    authentik = {
      source  = "goauthentik/authentik"
      version = "2025.10.1"
    }

  }
}

provider "authentik" {
  url   = "https://auth.${var.public_domain}"
  token = var.authentik_token
}

terraform {
  cloud {
    organization = "chaijunkin"
    workspaces { name = "authentik-workspace" }
  }
}

# terraform {
#   backend "s3" {
#     bucket   = "tf-state-bucket-cloudjur-com"
#     key      = "authentik.terraform.tfstate"
#     use_lockfile = true
#     endpoints = {
#       s3 = "https://8550295d25a8172e9fe4f9f7a7f327be.r2.cloudflarestorage.com"
#     }

#     region                      = "auto"
#     skip_credentials_validation = true
#     skip_metadata_api_check     = true
#     skip_region_validation      = true
#     skip_requesting_account_id  = true
#     skip_s3_checksum            = true
#     use_path_style              = true
#   }
#   # cloud {
#   #   organization = "chaijunkin"
#   #   workspaces { name = "authentik-workspace" }
#   # }
# }