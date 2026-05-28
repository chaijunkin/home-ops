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
  website_access_enabled = true
  # website_config_index_document = "index.html"
  # website_config_error_document = "error.html"

  providers = {
    garage = garage
  }
}

# Admin key for managing staticgarage buckets
resource "garage_key" "admin_key" {
  name = "admin-user"
}
