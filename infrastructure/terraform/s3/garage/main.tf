locals {
  buckets = [
    # "loki",
    # "thanos",
    # "ocis",
    # "volsync",
    "dragonfly",
    "postgresql",
    "opencloud",
    "wiki",
    "schema",
    # "tempo"
  ]
}
# Create buckets dynamically using the garage module
module "buckets" {
  for_each    = toset(local.buckets)
  source      = "./modules/garage"
  bucket_name = each.key
  admin_user  = garage_key.admin_key.id
  website_access_enabled = (each.key == "wiki" || each.key == "schema") ? true : false

  providers = {
    garage = garage
  }
}

# Admin key for managing garage buckets
resource "garage_key" "admin_key" {
  name = "admin-user"
}