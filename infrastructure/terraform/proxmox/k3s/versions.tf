terraform {
  required_providers {
    proxmox = {
      source  = "Telmate/proxmox"
      version = "3.0.1-rc3"
    }
  }
  required_version = ">= 0.13"
}

### DONT APPLY, breaking change