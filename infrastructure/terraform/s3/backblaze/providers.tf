terraform {
  backend "s3" {
    bucket       = "tf-state-bucket-cloudjur-com"
    key          = "backblaze.terraform.tfstate"
    use_lockfile = true
    endpoints = {
      s3 = "https://8550295d25a8172e9fe4f9f7a7f327be.r2.cloudflarestorage.com"
    }

    region                      = "auto"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
  required_providers {
    b2 = {
      source  = "Backblaze/b2"
      version = "0.12.0"
    }
  }
}


provider "b2" {

  application_key    = var.b2_application_key
  application_key_id = var.b2_application_key_id

}
