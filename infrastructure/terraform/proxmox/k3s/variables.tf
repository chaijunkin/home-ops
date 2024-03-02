#-------------------------------------------------------------------------------------------#
# Proxmox Variables 
# Reference: https://github.com/Telmate/terraform-provider-proxmox/blob/master/docs/index.md
#-------------------------------------------------------------------------------------------#

variable "proxmox_api_url" {
  description = "This is the target Proxmox API endpoint"
  type        = string
}

variable "proxmox_api_user" {
  description = "This is the Proxmox API user. Use root@pam or custom. Will need PVEDatastoreUser, PVEVMAdmin, PVETemplateUser permissions"
  type        = string
  sensitive   = true
  default     = "root@pam"
}

variable "proxmox_api_pass" {
  description = "API user password. Required, sensitive, or use environment variable TF_VAR_proxmox_api_pass"
  sensitive   = true
}

variable "proxmox_ignore_tls" {
  description = "Disable TLS verification while connecting"
  type        = string
  default     = "true"
}


# -- Common Variables -- #

# variable "desc" {
#   description = "Description of the variable"
# }

# variable "full_clone" {
#   description = "Whether to perform a full clone or not"
# }

variable "default_image_username" {
  description = "Default username for the image"
}

variable "default_image_password" {
  description = "Default password for the image"
}

variable "nameserver" {
  description = "Nameserver for DNS resolution"
}

variable "searchdomain" {
  description = "Search domain for DNS resolution"
}

# variable "onboot" {
#   description = "Specifies whether the VM should start up automatically or not"
# }

# variable "boot" {
#   description = "Boot options for the VM"
# }

# variable "vm_sockets" {
#   description = "Number of sockets for the VM"
# }

variable "k3sserver_vm_cores" {
  description = "Number of cores for the VM"
}

# variable "agent" {
#   description = "Agent configuration"
# }

# variable "terraform_provisioner_type" {
#   description = "Type of provisioner used by Terraform"
# }

# # -- k3s Server Node VM Var -- #

variable "k3sserver_target_node" {
  description = "Target node for k3s server"
}

variable "k3sserver_clone" {
  description = "Whether to clone k3s server or not"
}

variable "k3sserver_vm_name_prefix" {
  description = "Prefix for the k3s server VM name"
  default     = "k3s_master"
}

variable "k3sserver_vm_memory" {
  description = "Memory for the k3s server VM"
}

variable "k3sserver_ip_addresses" {
  description = "IP addresses for the k3s server VM"
}

variable "k3sserver_ip_cidr" {
  description = "CIDR notation for the IP address of the k3s server VM"
  default     = "/24"
}

variable "k3sserver_gw" {
  description = "Gateway for the k3s server VM"
}

variable "k3sserver_vm_network" {
  description = "Network configuration for the k3s server VM"
  # default = [
  #   {
  #     model  = "virtio"
  #     bridge = "vmbr0"
  #     tag    = null
  #   },
  # ]
}

variable "k3sserver_vm_disk" {
  description = "Disk configuration for the k3s server VM"
  # default = [
  #   {
  #     type    = "scsi"
  #     storage = "vm-store"
  #     size    = "100G"
  #     format  = "qcow2"
  #     ssd     = 0
  #   },
  # ]
}

variable "k3sworker_target_node" {
  type        = string
  description = "The target node for the K3s worker."
}

variable "k3sworker_clone" {
  type        = string
  description = "Boolean indicating whether to clone the K3s worker."
}

variable "k3sworker_vm_name_prefix" {
  type        = string
  description = "Prefix for the name of the K3s worker VM."
  default     = "k3s_worker"
}

variable "k3sworker_vm_memory" {
  type        = number
  description = "Amount of memory (in MB) allocated to the K3s worker VM."
}

variable "k3sworker_vm_cores" {
  type        = number
  description = "Number of CPU cores allocated to the K3s worker VM."
}

variable "k3sworker_ip_addresses" {
  description = "IP address of the K3s worker."
}

variable "k3sworker_ip_cidr" {
  type        = string
  description = "CIDR notation for the IP address range of the K3s worker."
  default     = "/24"
}

variable "k3sworker_gw" {
  type        = string
  description = "Gateway for the K3s worker."
}

variable "k3sworker_vm_network" {
  description = "Configuration for the network settings of the K3s worker VM."
}

variable "k3sworker_vm_disk" {
  description = "Configuration for the disk settings of the K3s worker VM."
}

variable "ssh_public_keys" {
  type        = string
  description = "List of SSH public keys for accessing the K3s worker VM."
}
