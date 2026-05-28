terraform {
  required_providers {
    garage = {
      source = "schwitzd/garage"
      version = "1.2.2"
    }
  }
}

resource "garage_bucket" "bucket" {
  global_alias = var.bucket_name
  website_access_enabled = var.website_access_enabled
  website_config_index_document = var.website_access_enabled ? "index.html" : var.website_config_index_document
  website_config_error_document = var.website_access_enabled ? "error.html" : var.website_config_error_document

}

resource "garage_key" "access_key" {
  name = "${var.bucket_name}-key"
}

resource "garage_bucket_alias" "bucket_alias" {
  count = var.create_alias ? 1 : 0
  bucket_id    = garage_bucket.bucket.id
  global_alias = format("%s.cloudjur.com", var.bucket_name)
}
# I wish the op provider would allow me to write
# those fields in to an existing secret...
resource "garage_bucket_key" "bucket_key" {
  access_key_id = garage_key.access_key.id
  bucket_id     = garage_bucket.bucket.id
  owner         = true
  read          = true
  write         = true
}

resource "garage_bucket_key" "admin_user" {
  access_key_id = var.admin_user
  bucket_id     = garage_bucket.bucket.id
  owner         = true
  read          = true
  write         = true
}