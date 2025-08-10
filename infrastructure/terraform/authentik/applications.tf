locals {
  oauth_apps = [
    # "dashbrr",
    "grafana",
    "headlamp",
    # "kyoo",
    # "lubelogger",
    "open-webui",
    # "paperless",
    # "portainer"
  ]
}

locals {
  applications = {
    # dashbrr = {
    #   client_id     = module.onepassword_application["dashbrr"].fields["DASHBRR_CLIENT_ID"]
    #   client_secret = module.onepassword_application["dashbrr"].fields["DASHBRR_CLIENT_SECRET"]
    #   group         = "downloads"
    #   icon_url      = "https://raw.githubusercontent.com/joryirving/home-ops/main/docs/src/assets/icons/dashbrr.png"
    #   redirect_uri  = "https://dashbrr.${var.CLUSTER_DOMAIN}/api/auth/callback"
    #   launch_url    = "https://dashbrr.${var.CLUSTER_DOMAIN}/api/auth/callback"
    # },
    grafana = {
      client_id     = var.grafana_id
      client_secret = var.grafana_secret
      group         = "monitoring"
      icon_url      = "https://raw.githubusercontent.com/homarr-labs/dashboard-icons/main/png/grafana.png"
      redirect_uri  = "https://grafana.${var.CLUSTER_DOMAIN}/login/generic_oauth"
      launch_url    = "https://grafana.${var.CLUSTER_DOMAIN}/login/generic_oauth"
    },
    headlamp = {
      client_id     = var.headlamp_id
      client_secret = var.headlamp_secret
      group         = "infrastructure"
      icon_url      = "https://raw.githubusercontent.com/headlamp-k8s/headlamp/refs/heads/main/frontend/src/resources/icon-dark.svg"
      redirect_uri  = "https://headlamp.${var.CLUSTER_DOMAIN}/oidc-callback"
      launch_url    = "https://headlamp.${var.CLUSTER_DOMAIN}/"
    },
    # kyoo = {
    #   client_id     = module.onepassword_application["kyoo"].fields["KYOO_CLIENT_ID"]
    #   client_secret = module.onepassword_application["kyoo"].fields["KYOO_CLIENT_SECRET"]
    #   group         = "media"
    #   icon_url      = "https://raw.githubusercontent.com/zoriya/Kyoo/master/icons/icon-256x256.png"
    #   redirect_uri  = "https://kyoo.${var.CLUSTER_DOMAIN}/api/auth/logged/authentik"
    #   launch_url    = "https://kyoo.${var.CLUSTER_DOMAIN}/api/auth/login/authentik?redirectUrl=https://kyoo.${var.CLUSTER_DOMAIN}/login/callback"
    # },
    # lubelogger = {
    #   client_id     = module.onepassword_application["lubelogger"].fields["LUBELOGGER_CLIENT_ID"]
    #   client_secret = module.onepassword_application["lubelogger"].fields["LUBELOGGER_CLIENT_SECRET"]
    #   group         = "home"
    #   icon_url      = "https://demo.lubelogger.com/defaults/lubelogger_icon_72.png"
    #   redirect_uri  = "https://lubelogger.${var.CLUSTER_DOMAIN}/Login/RemoteAuth"
    #   launch_url    = "https://lubelogger.${var.CLUSTER_DOMAIN}/Login/RemoteAuth"
    # },
    open-webui = {
      client_id     = var.open_webui_id
      client_secret = var.open_webui_secret
      group         = "home"
      icon_url      = "https://raw.githubusercontent.com/open-webui/open-webui/refs/heads/main/static/favicon.png"
      redirect_uri  = "https://chat.${var.CLUSTER_DOMAIN}/oauth/oidc/callback"
      launch_url    = "https://chat.${var.CLUSTER_DOMAIN}/auth"
    },
    # paperless = {
    #   client_id     = module.onepassword_application["paperless"].fields["PAPERLESS_CLIENT_ID"]
    #   client_secret = module.onepassword_application["paperless"].fields["PAPERLESS_CLIENT_SECRET"]
    #   group         = "home"
    #   icon_url      = "https://raw.githubusercontent.com/homarr-labs/dashboard-icons/main/png/paperless.png"
    #   redirect_uri  = "https://paperless.${var.CLUSTER_DOMAIN}/accounts/oidc/authentik/login/callback/"
    #   launch_url    = "https://paperless.${var.CLUSTER_DOMAIN}/"
    # },
    # portainer = {
    #   client_id     = module.onepassword_application["portainer"].fields["PORTAINER_CLIENT_ID"]
    #   client_secret = module.onepassword_application["portainer"].fields["PORTAINER_CLIENT_SECRET"]
    #   group         = "infrastructure"
    #   icon_url      = "https://raw.githubusercontent.com/homarr-labs/dashboard-icons/main/png/portainer.png"
    #   redirect_uri  = "https://portainer.${var.CLUSTER_DOMAIN}/"
    #   launch_url    = "https://portainer.${var.CLUSTER_DOMAIN}/"
    # }
  }
}

resource "authentik_provider_oauth2" "oauth2" {
  for_each              = local.applications
  name                  = each.key
  client_id             = each.value.client_id
  client_secret         = each.value.client_secret
  authorization_flow    = authentik_flow.provider-authorization-implicit-consent.uuid
  authentication_flow   = authentik_flow.authentication.uuid
  invalidation_flow     = data.authentik_flow.default-provider-invalidation-flow.id
  property_mappings     = data.authentik_property_mapping_provider_scope.oauth2.ids
  access_token_validity = "hours=4"
  signing_key           = data.authentik_certificate_key_pair.generated.id
  allowed_redirect_uris = [
    {
      matching_mode = "strict",
      url           = each.value.redirect_uri,
    }
  ]
}

resource "authentik_application" "application" {
  for_each           = local.applications
  name               = title(each.key)
  slug               = each.key
  protocol_provider  = authentik_provider_oauth2.oauth2[each.key].id
  group              = authentik_group.default[each.value.group].name
  open_in_new_tab    = true
  meta_icon          = each.value.icon_url
  meta_launch_url    = each.value.launch_url
  policy_engine_mode = "all"
}
