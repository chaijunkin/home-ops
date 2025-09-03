terraform {
  required_providers {
    authentik = {
      source  = "goauthentik/authentik"
      version = "2025.8.0"
    }

  }
}

provider "authentik" {
  url   = "https://auth.${var.CLUSTER_DOMAIN}"
  token = var.authentik_token
}
