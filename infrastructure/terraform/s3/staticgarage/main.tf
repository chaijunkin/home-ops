locals {
  buckets = [
    "wiki",
    "schema"
  ]
}

# Create buckets dynamically using the garage module from the original garage folder
module "buckets" {
  for_each    = toset(local.buckets)
  source      = "../garage/modules/garage"
  bucket_name = each.key
  admin_user  = garage_key.admin_key.id
  create_alias = true

  providers = {
    garage = garage
  }
}

# Admin key for managing staticgarage buckets
resource "garage_key" "admin_key" {
  name = "admin-user"
}
