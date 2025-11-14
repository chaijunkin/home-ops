## NOT SUPPORTED YET IN CILIUM
locals {
  proxy = [
    # {
    #   name     = "n8n"
    #   icon_url = "https://raw.githubusercontent.com/chaijunkin/dashboard-icons/b76499ba5f7a70614758cfe5bd9bb7cb514d8ff9/svg/n8n.svg"
    #   description = "Workflow automation tool"
    #   group = "automation"
    #   slug = "n8n"
    #   auth_groups = [authentik_group.default["infrastructure"].id]
    # }
    {
      name        = "echo-server-ext-auth"
      icon_url    = "https://raw.githubusercontent.com/chaijunkin/dashboard-icons/main/png/web-check.png"
      description = ""
      group       = "home"
      slug        = "echo-server-ext-auth"
      auth_groups = [authentik_group.default["home"].id]
    },
    {
      name        = "echo-server-int-auth"
      icon_url    = "https://raw.githubusercontent.com/chaijunkin/dashboard-icons/main/png/web-check.png"
      description = ""
      group       = "home"
      slug        = "echo-server-int-auth"
      auth_groups = [authentik_group.default["home"].id]
    }
  ]
}

module "proxy" {

  for_each = { for proxy in local.proxy : proxy.name => proxy }

  source = "./modules/proxy_application"

  name               = each.value.name
  description        = each.value.description
  icon_url           = each.value.icon_url
  group              = authentik_group.default[each.value.group].name
  slug               = each.value.slug
  domain             = var.public_domain
  authorization_flow = resource.authentik_flow.provider-authorization-implicit-consent.uuid
  invalidation_flow  = resource.authentik_flow.provider-invalidation.uuid
  auth_groups        = each.value.auth_groups
}

# data "authentik_service_connection_kubernetes" "local" {
#   name = "Local Kubernetes Cluster"
# }

# resource "authentik_outpost" "proxy" {
#   name = "proxy"
#   protocol_providers = values(module.proxy)[*].id
#   service_connection = data.authentik_service_connection_kubernetes.local.id
# }

locals {
  applications = {
    grafana = {
      client_id     = var.grafana_id
      client_secret = var.grafana_secret
      group         = "monitoring"
      icon_url      = "https://raw.githubusercontent.com/homarr-labs/dashboard-icons/main/png/grafana.png"
      redirect_uri  = "https://grafana.${var.public_domain}/login/generic_oauth"
      launch_url    = "https://grafana.${var.public_domain}/login/generic_oauth"
    },
    headlamp = {
      client_id     = var.headlamp_id
      client_secret = var.headlamp_secret
      group         = "infrastructure"
      icon_url      = "https://raw.githubusercontent.com/headlamp-k8s/headlamp/refs/heads/main/frontend/src/resources/icon-dark.svg"
      redirect_uri  = "https://headlamp.${var.public_domain}/oidc-callback"
      launch_url    = "https://headlamp.${var.public_domain}/"
    },
    romm = {
      client_id     = var.romm_id
      client_secret = var.romm_secret
      group         = "media"
      icon_url      = "https://raw.githubusercontent.com/chaijunkin/dashboard-icons/b76499ba5f7a70614758cfe5bd9bb7cb514d8ff9/svg/romm.svg"
      redirect_uri  = "https://romm.${var.public_domain}/api/oauth/openid"
      launch_url    = "https://romm.${var.public_domain}/"
    },
    jellyfin = {
      client_id     = var.jellyfin_id
      client_secret = var.jellyfin_secret
      group         = "media"
      icon_url      = "https://raw.githubusercontent.com/chaijunkin/dashboard-icons/b76499ba5f7a70614758cfe5bd9bb7cb514d8ff9/svg/jellyfin.svg"
      redirect_uri  = "https://jellyfin.${var.public_domain}/sso/OID/redirect/authentik"
      launch_url    = "https://jellyfin.${var.public_domain}/sso/OID/start/authentik"
    },
    open-webui = {
      client_id     = var.open_webui_id
      client_secret = var.open_webui_secret
      group         = "home"
      icon_url      = "https://raw.githubusercontent.com/open-webui/open-webui/refs/heads/main/static/favicon.png"
      redirect_uri  = "https://chat.${var.public_domain}/oauth/oidc/callback"
      launch_url    = "https://chat.${var.public_domain}/auth"
    },
    calibre-web-automated = {
      client_id     = var.calibre_web_automated_id
      client_secret = var.calibre_web_automated_secret
      group         = "media"
      icon_url      = "https://raw.githubusercontent.com/chaijunkin/dashboard-icons/refs/heads/main/png/calibre-web.png"
      redirect_uri  = "https://books.${var.public_domain}/oauth/oidc/callback"
      launch_url    = "https://books.${var.public_domain}/auth"
    },
    karakeep = {
      client_id     = var.karakeep_id
      client_secret = var.karakeep_secret
      group         = "home"
      icon_url      = "https://raw.githubusercontent.com/chaijunkin/dashboard-icons/refs/heads/main/png/karakeep.png"
      redirect_uri  = "https://karakeep.${var.public_domain}/api/auth/callback/custom"
      launch_url    = "https://karakeep.${var.public_domain}/auth"
    },
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

module "oauth2-opencloud" {
  source             = "./modules/oauth2_application"
  name               = "OpenCloud"
  icon_url           = "https://raw.githubusercontent.com/chaijunkin/dashboard-icons/b76499ba5f7a70614758cfe5bd9bb7cb514d8ff9/svg/opencloud.svg"
  launch_url         = "https://drive.cloudjur.com"
  description        = "OpenCloud"
  newtab             = true
  group              = "Media"
  auth_groups        = [authentik_group.default["media"].id]
  client_type        = "public"
  authorization_flow = resource.authentik_flow.provider-authorization-implicit-consent.uuid
  invalidation_flow  = resource.authentik_flow.provider-invalidation.uuid
  client_id          = "web"
  # client_id          = var.ocis_id
  # client_secret = var.ocis_secret
  # additional_property_mappings = formatlist(authentik_scope_mapping.openid-nextcloud.id)
  redirect_uris = [
    "https://drive.cloudjur.com",
    "https://drive.cloudjur.com/oidc-callback.html",
    "https://drive.cloudjur.com/oidc-silent-redirect.html"
  ]
}

module "oauth2-opencloud-android" {
  source             = "./modules/oauth2_application"
  name               = "OpenCloudAndroid"
  launch_url         = "blank://blank"
  auth_groups        = [authentik_group.default["media"].id]
  authorization_flow = resource.authentik_flow.provider-authorization-implicit-consent.uuid
  invalidation_flow  = data.authentik_flow.default-provider-invalidation-flow.id
  client_id          = "OpenCloudAndroid"
  # client_secret      = "dInFYGV33xKzhbRmpqQltYNdfLdJIfJ9L5ISoKhNoT9qZftpdWSP71VrpGR9pmoD"
  redirect_uris = ["oc://android.opencloud.eu"]
}

module "oauth2-opencloud-desktop" {
  source             = "./modules/oauth2_application"
  name               = "OpenCloudDesktop"
  launch_url         = "blank://blank"
  auth_groups        = [authentik_group.default["media"].id]
  authorization_flow = resource.authentik_flow.provider-authorization-implicit-consent.uuid
  invalidation_flow  = data.authentik_flow.default-provider-invalidation-flow.id
  client_id          = "OpenCloudDesktop"
  # client_secret      = "UBntmLjC2yYCeHwsyj73Uwo9TAaecAetRwMw0xYcvNL9yRdLSUi0hUAHfvCHFeFh"
  redirect_uris = [
    { matching_mode = "regex", url = "http://127.0.0.1(:.*)?" },
    { matching_mode = "regex", url = "http://localhost(:.*)?" }
  ]
}

module "oauth2-opencloud-ios" {
  source             = "./modules/oauth2_application"
  name               = "OpenCloudIOS"
  launch_url         = "blank://blank"
  auth_groups        = [authentik_group.default["media"].id]
  client_type        = "public"
  authorization_flow = resource.authentik_flow.provider-authorization-implicit-consent.uuid
  invalidation_flow  = resource.authentik_flow.provider-invalidation.uuid
  client_id          = "OpenCloudIOS"
  redirect_uris      = ["oc://ios.opencloud.eu"]
}