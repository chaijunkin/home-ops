resource "authentik_group" "users" {
  name         = "users"
  is_superuser = false
}

resource "authentik_group" "downloads" {
  name         = "Downloads"
  is_superuser = false
}

resource "authentik_group" "home" {
  name         = "Home"
  is_superuser = false
}

# resource "authentik_policy_binding" "paperless_monitoring" {
#   target = authentik_application.paperless_application.uuid
#   group  = authentik_group.home.id
#   order  = 0
# }

resource "authentik_group" "infrastructure" {
  name         = "Infrastructure"
  is_superuser = false
}

# resource "authentik_policy_binding" "gitops_infra" {
#   target = authentik_application.gitops_application.uuid
#   group  = authentik_group.infrastructure.id
#   order  = 0
# }

# resource "authentik_policy_binding" "portainer_infra" {
#   target = authentik_application.portainer_application.uuid
#   group  = authentik_group.infrastructure.id
#   order  = 0
# }

resource "authentik_group" "media" {
  name         = "Media"
  is_superuser = false
  parent       = resource.authentik_group.users.id
}

resource "authentik_group" "grafana_admin" {
  name         = "Grafana Admins"
  is_superuser = false
}

resource "authentik_policy_binding" "grafana_admins" {
  target = authentik_application.grafana_application.uuid
  group  = authentik_group.grafana_admin.id
  order  = 0
}

resource "authentik_group" "monitoring" {
  name         = "Monitoring"
  is_superuser = false
  parent       = resource.authentik_group.grafana_admin.id
}

resource "authentik_policy_binding" "grafana_infra" {
  target = authentik_application.grafana_application.uuid
  group  = authentik_group.monitoring.id
  order  = 0
}

data "authentik_group" "admins" {
  name = "authentik Admins"
}

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