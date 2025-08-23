locals {
  oauth_apps = [
    # "dashbrr",
    "grafana",
    "headlamp",
    "ocis",
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
    # drive = {  # owncloud
    #   client_id     = var.ocis_id
    #   client_secret = var.ocis_secret
    #   group         = "media"
    #   icon_url      = "https://raw.githubusercontent.com/chaijunkin/dashboard-icons/b76499ba5f7a70614758cfe5bd9bb7cb514d8ff9/svg/owncloud.svg"
    #   redirect_uri  = "https://drive.${var.CLUSTER_DOMAIN}/oauth/oidc/callback"
    #   launch_url    = "https://drive.${var.CLUSTER_DOMAIN}/"
    # },
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

module "oauth2-ocis" {
  source             = "./modules/oauth2_application"
  name               = "Owncloud"
  icon_url           = "https://raw.githubusercontent.com/chaijunkin/dashboard-icons/b76499ba5f7a70614758cfe5bd9bb7cb514d8ff9/svg/owncloud.svg"
  launch_url         = "https://drive.cloudjur.com"
  description        = "ownCloud Infinite Scale"
  newtab             = true
  group              = "Media"
  auth_groups        = [authentik_group.default["media"].id]
  client_type        = "public"
  authorization_flow = resource.authentik_flow.provider-authorization-implicit-consent.uuid
  invalidation_flow  = data.authentik_flow.default-provider-invalidation-flow.id
  client_id          = var.ocis_id
  client_secret      = var.ocis_secret
  # additional_property_mappings = formatlist(authentik_scope_mapping.openid-nextcloud.id)
  redirect_uris = [
    "https://drive.cloudjur.com",
    "https://drive.cloudjur.com/oidc-callback.html",
    "https://drive.cloudjur.com/oidc-silent-redirect.html"
  ]
}

module "oauth2-ocis-android" {
  source             = "./modules/oauth2_application"
  name               = "Owncloud-android"
  launch_url         = "blank://blank"
  auth_groups        = [authentik_group.default["media"].id]
  authorization_flow = resource.authentik_flow.provider-authorization-implicit-consent.uuid
  invalidation_flow  = data.authentik_flow.default-provider-invalidation-flow.id
  client_id          = "e4rAsNUSIUs0lF4nbv9FmCeUkTlV9GdgTLDH1b5uie7syb90SzEVrbN7HIpmWJeD"
  client_secret      = "dInFYGV33xKzhbRmpqQltYNdfLdJIfJ9L5ISoKhNoT9qZftpdWSP71VrpGR9pmoD"
  redirect_uris      = ["oc://android.owncloud.com"]
}

module "oauth2-ocis-desktop" {
  source             = "./modules/oauth2_application"
  name               = "Owncloud-desktop"
  launch_url         = "blank://blank"
  auth_groups        = [authentik_group.default["media"].id]
  authorization_flow = resource.authentik_flow.provider-authorization-implicit-consent.uuid
  invalidation_flow  = data.authentik_flow.default-provider-invalidation-flow.id
  client_id          = "xdXOt13JKxym1B1QcEncf2XDkLAexMBFwiT9j6EfhhHFJhs2KM9jbjTmf8JBXE69"
  client_secret      = "UBntmLjC2yYCeHwsyj73Uwo9TAaecAetRwMw0xYcvNL9yRdLSUi0hUAHfvCHFeFh"
  redirect_uris = [
    { matching_mode = "regex", url = "http://127.0.0.1(:.*)?" },
    { matching_mode = "regex", url = "http://localhost(:.*)?" }
  ]
}