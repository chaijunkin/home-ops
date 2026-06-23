terraform {
  required_providers {
    authentik = {
      source  = "goauthentik/authentik"
      version = "2026.5.0" # 2026.2.0 has bugged for system_setting enterprise_audit_include_expanded_diff
    }
    # bitwarden-secrets = {
    #   source = "registry.terraform.io/bitwarden/bitwarden-secrets"
    # }
  }

  backend "s3" {
    bucket   = "tf-state-bucket-cloudjur-com"
    key      = "authentik.terraform.tfstate"
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

provider "authentik" {
  url   = "https://auth.${var.public_domain}"
  token = var.authentik_token
}

# provider "bitwarden-secrets" {
#   api_url         = "https://api.bitwarden.com"
#   identity_url    = "https://identity.bitwarden.com"
#   # access_token    = "< secret machine account access token >" # BW_ACCESS_TOKEN
#   # organization_id = "< your organization uuid >" # BW_ORGANIZATION_ID
# }