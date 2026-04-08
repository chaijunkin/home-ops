locals {
  buckets = [
    # "loki",
    # "thanos",
    # "ocis",
    # "volsync",
    # "postgresql",
    # "opencloud"
    "tempo"
  ]
}

module "garage_bucket" {
  for_each    = toset(local.buckets)
  source      = "./modules/garage"
  bucket_name = each.key
  # user_name   = random_password.user_name[each.key].result
  access_key = random_password.access_key[each.key].result
  secret_key = random_password.secret_key[each.key].result
  # owner_access_key = var.owner_access_key
  # owner_secret_key = var.owner_secret_key
  providers = {
    garage = garage
  }
}

output "garage_bucket_outputs" {
  value     = module.garage_bucket
  sensitive = true
}

resource "random_password" "user_name" {
  for_each = toset(local.buckets)
  length   = 32
  special  = false
}

resource "random_password" "access_key" {
  for_each = toset(local.buckets)
  length   = 64
}

resource "random_password" "secret_key" {
  for_each = toset(local.buckets)
  length   = 64
}