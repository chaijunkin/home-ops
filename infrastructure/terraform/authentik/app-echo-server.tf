resource "authentik_group" "echo_server_users" {
  name = "Echo Server Users"
}

module "echo_server_internal" {
  source = "./modules/forward-auth-application"
  slug   = "echo_server_internal"

  name   = "Echo Server"
  domain = "echo-server-internal.${var.cluster_domain}"
  group  = authentik_group.infrastructure.name

  policy_engine_mode      = "any"
  authorization_flow_uuid = data.authentik_flow.default-provider-authorization-implicit-consent.id

  meta_icon = "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/web-check.png"
}

resource "authentik_policy_binding" "echo_server-access-users" {
  target = module.echo_server_internal.application_id
  group  = authentik_group.echo_server_users.id
  order  = 0
}

module "echo_server_external" {
  source = "./modules/forward-auth-application"
  slug   = "echo_server_external"

  name   = "Echo Server External"
  domain = "echo-server-external.${var.cluster_domain}"
  group  = authentik_group.infrastructure.name

  policy_engine_mode      = "any"
  authorization_flow_uuid = data.authentik_flow.default-provider-authorization-implicit-consent.id

  meta_icon = "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/web-check.png"
}

resource "authentik_policy_binding" "echo_server-external-access-users" {
  target = module.echo_server_external.application_id
  group  = authentik_group.echo_server_users.id
  order  = 0
}