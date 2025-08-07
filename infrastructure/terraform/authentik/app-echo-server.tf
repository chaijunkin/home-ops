
module "echo_server_internal" {
  source = "./modules/forward-auth-application"
  slug   = "echo_server_internal"

  name   = "Echo Server"
  domain = "echo-server-internal.${var.CLUSTER_DOMAIN}"
  group  = authentik_group.default["infrastructure"].id

  policy_engine_mode        = "any"
  authorization_flow_uuid   = authentik_flow.provider-authorization-implicit-consent.uuid
  invalidation_flow_uuid    = data.authentik_flow.default-provider-invalidation-flow.id

  meta_icon = "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/web-check.png"
}

resource "authentik_policy_binding" "echo_server-access-users" {
  target = module.echo_server_internal.application_id
  group  = authentik_group.default["infrastructure"].id
  order  = 0
}

module "echo_server_external" {
  source = "./modules/forward-auth-application"
  slug   = "echo_server_external"

  name   = "Echo Server External"
  domain = "echo-server-external.${var.CLUSTER_DOMAIN}"
  group  = authentik_group.default["infrastructure"].id

  policy_engine_mode        = "any"
  authorization_flow_uuid   = authentik_flow.provider-authorization-implicit-consent.uuid
  invalidation_flow_uuid    = data.authentik_flow.default-provider-invalidation-flow.id

  meta_icon = "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/web-check.png"
}

resource "authentik_policy_binding" "echo_server-external-access-users" {
  target = module.echo_server_external.application_id
  group  = authentik_group.default["infrastructure"].id
  order  = 0
}