terraform {
  cloud {
    organization = "chaijunkin"
    workspaces { name = "b2-workspace" }
  }
  required_providers {
    b2 = {
      source  = "Backblaze/b2"
      version = "0.8.12"
    }
  }
}


provider "b2" {

  application_key    = var.b2_application_key
  application_key_id = var.b2_application_key_id

}