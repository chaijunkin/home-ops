### NOT SUPPORTED YET IN CILIUM
# locals {
#   proxy = [
#     {
#       name     = "n8n"
#       icon_url = "https://raw.githubusercontent.com/chaijunkin/dashboard-icons/b76499ba5f7a70614758cfe5bd9bb7cb514d8ff9/svg/n8n.svg"
#       description = "Workflow automation tool"
#       group = "automation"
#       slug = "n8n"
#       auth_groups = [authentik_group.default["infrastructure"].id]
#     }
#   ]
# }

# module "proxy" {

#   for_each = { for proxy in local.proxy : proxy.name => proxy }

#   source = "./modules/proxy_application"

#   name               = each.value.name
#   description        = each.value.description
#   icon_url           = each.value.icon_url
#   group              = each.value.group
#   slug               = each.value.slug
#   domain             = var.CLUSTER_DOMAIN
#   authorization_flow = resource.authentik_flow.provider-authorization-implicit-consent.uuid
#   invalidation_flow  = resource.authentik_flow.provider-invalidation.uuid
#   auth_groups        = each.value.auth_groups
# }

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
    jellyfin = {
      client_id     = var.jellyfin_id
      client_secret = var.jellyfin_secret
      group         = "media"
      icon_url      = "https://raw.githubusercontent.com/chaijunkin/dashboard-icons/b76499ba5f7a70614758cfe5bd9bb7cb514d8ff9/svg/jellyfin.svg"
      redirect_uri  = "https://jellyfin.${var.CLUSTER_DOMAIN}/sso/OID/redirect/authentik"
      launch_url    = "https://jellyfin.${var.CLUSTER_DOMAIN}/sso/OID/start/authentik"
    },
    open-webui = {
      client_id     = var.open_webui_id
      client_secret = var.open_webui_secret
      group         = "home"
      icon_url      = "https://raw.githubusercontent.com/open-webui/open-webui/refs/heads/main/static/favicon.png"
      redirect_uri  = "https://chat.${var.CLUSTER_DOMAIN}/oauth/oidc/callback"
      launch_url    = "https://chat.${var.CLUSTER_DOMAIN}/auth"
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