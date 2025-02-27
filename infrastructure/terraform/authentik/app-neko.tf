resource "authentik_group" "movienight_users" {
  name = "movienight Users"
}

# module "movienight" {
#   source = "./modules/forward-auth-application"
#   slug   = "movienight_internal"

#   name   = "movienight"
#   domain = "movienight.${var.cluster_domain}"
#   group  = authentik_group.infrastructure.name

#   policy_engine_mode      = "any"
#   authorization_flow_uuid = data.authentik_flow.default-provider-authorization-implicit-consent.id

#   meta_icon = "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/web-check.png"
# }

# resource "authentik_policy_binding" "movienight-access-users" {
#   target = module.movienight_internal.application_id
#   group  = authentik_group.movienight_users.id
#   order  = 0
# }

module "movienight_external" {
  source = "./modules/forward-auth-application"
  slug   = "movienight_external"

  name   = "movienight External"
  domain = "movienight.${var.cluster_domain}"
  group  = authentik_group.infrastructure.name

  policy_engine_mode      = "any"
  authorization_flow_uuid = data.authentik_flow.default-provider-authorization-implicit-consent.id

  meta_icon = "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/neko.png"
}

resource "authentik_policy_binding" "movienight-external-access-users" {
  target = module.movienight_external.application_id
  group  = authentik_group.movienight_users.id
  order  = 0
}