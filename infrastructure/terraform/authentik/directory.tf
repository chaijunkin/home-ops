locals {
  authentik_groups = {
    downloads      = { name = "Downloads" }
    home           = { name = "Home" }
    infrastructure = { name = "Infrastructure" }
    media          = { name = "Media" }
    monitoring     = { name = "Monitoring" }
    users          = { name = "users" }
    superusers     = { name = "superusers" }
  }
}

data "authentik_user" "akadmin" {
  username = "akadmin"
}

data "authentik_group" "admins" {
  name = "authentik Admins"
}

resource "authentik_group" "grafana_admin" {
  name         = "Grafana Admins"
  is_superuser = false
  users        = [data.authentik_user.akadmin.id]
}

resource "authentik_group" "default" {
  for_each     = local.authentik_groups
  name         = each.value.name
  is_superuser = false
  users        = [data.authentik_user.akadmin.id]
}

resource "authentik_policy_binding" "application_policy_binding" {
  for_each = local.applications

  target = authentik_application.application[each.key].uuid
  group  = authentik_group.default[each.value.group].id
  order  = 0
}

# module "onepassword_discord" {
#   source = "github.com/joryirving/terraform-1password-item"
#   vault  = "Kubernetes"
#   item   = "discord"
# }

# ##Oauth
# resource "authentik_source_oauth" "discord" {
#   name                = "Discord"
#   slug                = "discord"
#   authentication_flow = data.authentik_flow.default-source-authentication.id
#   enrollment_flow     = authentik_flow.enrollment-invitation.uuid
#   user_matching_mode  = "email_deny"

#   provider_type   = "discord"
#   consumer_key    = module.onepassword_discord.fields["DISCORD_CLIENT_ID"]
#   consumer_secret = module.onepassword_discord.fields["DISCORD_CLIENT_SECRET"]
# }

#Oauth
resource "authentik_source_oauth" "google" {
  name                = "Google"
  slug                = "google"
  authentication_flow = data.authentik_flow.default-source-authentication.id
  enrollment_flow     = authentik_flow.enrollment-invitation.uuid
  user_matching_mode  = "email_link"

  provider_type   = "google"
  consumer_key    = var.oauth_client_id
  consumer_secret = var.oauth_client_secret

  access_token_url  = "https://oauth2.googleapis.com/token"
  authorization_url = "https://accounts.google.com/o/oauth2/v2/auth"
  oidc_jwks_url     = "https://www.googleapis.com/oauth2/v3/certs"
  profile_url       = "https://openidconnect.googleapis.com/v1/userinfo"
}
