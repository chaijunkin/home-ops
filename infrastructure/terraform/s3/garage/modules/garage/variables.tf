variable "bucket_name" {
  type = string
}

variable "admin_user" {
  type = string
}

variable "create_alias" {
  type    = bool
  default = false
}

variable "website_access_enabled" {
  type    = bool
  default = false
}

variable "website_config_index_document" {
  type    = string
  default = "index.html"
}

variable "website_config_error_document" {
  type    = string
  default = "error.html"
}