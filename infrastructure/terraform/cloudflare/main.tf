resource "cloudflare_r2_bucket" "tf_state_bucket" {
  account_id = local.cloudflare_account_id
  name       = "tf-state-bucket-cloudjur-com"
  location   = "APAC"
}

resource "cloudflare_zone" "cloudflare_zone" {
  account_id = local.cloudflare_account_id
  zone       = local.cloudflare_zone_name
}

resource "cloudflare_zone_dnssec" "cloudflare_zone_dnssec" {
  zone_id = cloudflare_zone.cloudflare_zone.id
}

resource "cloudflare_record" "records" {
  for_each = local.cloudflare_record
  zone_id  = cloudflare_zone.cloudflare_zone.id
  name     = each.value.name
  content  = each.value.value
  type     = each.value.type
  priority = try(each.value.priority, null)
  proxied  = try(each.value.proxied, false)
  ttl      = try(each.value.ttl, null)
}

resource "cloudflare_record" "github_A_record" {
  for_each = toset(local.github_A_record)
  zone_id  = cloudflare_zone.cloudflare_zone.id
  name     = "@"
  content  = each.value
  type     = "A"
  proxied  = true
}

resource "cloudflare_record" "github_AAAA_record" {
  for_each = toset(local.github_AAAA_record)
  zone_id  = cloudflare_zone.cloudflare_zone.id
  name     = "@"
  content  = each.value
  type     = "AAAA"
  proxied  = true
}

# resource "random_id" "tunnel_secret" {
#   byte_length = 35
# }

# resource "cloudflare_tunnel" "default" {
#   account_id = local.cloudflare_account_id
#   name       = "profile-cloudflare-tunnel"
#   secret     = random_id.tunnel_secret.b64_std
# }

# # Creates the CNAME record that routes http_app.${var.cloudflare_zone} to the tunnel.
# resource "cloudflare_record" "me" {
#   zone_id = cloudflare_zone.cloudflare_zone.id
#   name    = "me"
#   value   = "${cloudflare_tunnel.default.id}.cfargotunnel.com"
#   type    = "CNAME"
#   proxied = true
# }



# # Creates an Access application to control who can connect.
# resource "cloudflare_access_application" "profile_app" {
#   zone_id          = cloudflare_zone.cloudflare_zone.id
#   name             = "Access application for profile"
#   domain           = "me.${cloudflare_zone.cloudflare_zone.zone}"
#   type             = "self_hosted"
#   session_duration = "1h"
#   http_only_cookie_attribute = true
#   cors_headers {
#     allow_all_headers = true
#     allow_all_methods = true
#     allow_all_origins = true
#     allow_credentials = false
#     max_age           = 10
#   }
# }

# # Creates an Access policy for the application.
# resource "cloudflare_access_policy" "profile_policy" {
#   application_id = cloudflare_access_application.profile_app.id
#   zone_id        = cloudflare_zone.cloudflare_zone.id
#   name           = "profile policy for ${cloudflare_zone.cloudflare_zone.zone}"
#   precedence     = "1"
#   decision       = "allow"
#   include {
#     email = ["@gmail.com"]
#   }

#   include {
#     email_domain = ["@${local.cloudflare_zone_name}"]
#   }
# }

# resource "cloudflare_record" "public_ip" {
#   zone_id = cloudflare_zone.cloudflare_zone.id
#   name    = "traefik.${local.cloudflare_zone_name}"
#   value   = "192.168.1.249"
#   type    = "A"
# }

# resource "cloudflare_access_group" "default" {
#   account_id = local.cloudflare_account_id
#   name       = "myself group"

#   include {
#     email = ["@gmail.com"]
#   }

#   # include {
#   #   email_domain = ["@${local.cloudflare_zone_name}"]
#   # }
# }

# resource "cloudflare_record" "zoho_route_1" {
#   zone_id = cloudflare_zone.cloudflare_zone.id
#   name    = "_dmarc"
#   value   = "route1.mx.cloudflare.net"
#   type    = "MX"
#   priority = 8
# }

# resource "cloudflare_record" "zoho_route_1" {
#   zone_id = cloudflare_zone.cloudflare_zone.id
#   name    = "_dmarc"
#   value   = "route2.mx.cloudflare.net"
#   type    = "MX"
#   priority = 78
# }

# resource "cloudflare_record" "zoho_route_1" {
#   zone_id = cloudflare_zone.cloudflare_zone.id
#   name    = "_dmarc"
#   value   = "route3.mx.cloudflare.net"
#   type    = "MX"
#   priority = 95
# }

# resource "cloudflare_record" "zoho_spf" {
#   zone_id = cloudflare_zone.cloudflare_zone.id
#   name    = "@"
#   value   = "v=spf1 include:zoho.com ~all"
#   type    = "TXT"
# }
