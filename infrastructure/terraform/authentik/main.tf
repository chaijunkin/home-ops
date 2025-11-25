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
