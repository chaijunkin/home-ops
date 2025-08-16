variable "image" {
  description = "Talos image configuration"
  type = object({
    factory_url           = optional(string, "https://factory.talos.dev")
    schematic_path        = string
    version               = string
    update_schematic_path = optional(string)
    update_version        = optional(string)
    arch                  = optional(string, "amd64")
    platform              = optional(string, "nocloud")
    proxmox_datastore     = optional(string, "vm-store")
  })
}

variable "cluster" {
  description = "Cluster configuration"
  type = object({
    name                         = string
    vip                          = optional(string)
    gateway                      = string
    subnet_mask                  = optional(string, "24")
    talos_machine_config_version = optional(string)
    proxmox_cluster              = string
    kubernetes_version           = string
    gateway_api_version          = string
    extra_manifests              = optional(list(string))
    kubelet                      = optional(string)
    api_server                   = optional(string)
    cilium = object({
      bootstrap_manifest_path = string
      values_file_path        = string
    })
  })
}

variable "nodes" {
  description = "Configuration for cluster nodes"
  type = map(object({
    host_node    = string
    machine_type = string
    datastore_id = optional(string, "vm-store")
    ip           = string
    dns          = optional(list(string))
    dns_domain   = optional(string)
    network_devices = optional(list(object({
      mac_address = string
      tag         = optional(number)
      ip_address  = optional(string) # IP address for this specific interface
      gateway     = optional(string) # Gateway for this specific interface
    })), [])
    disk_iothread    = optional(bool, true)
    disk_cache       = optional(string, "writethrough")
    disk_discard     = optional(string, "on")
    disk_ssd         = optional(bool, true)
    disk_file_format = optional(string, "raw")
    disk_size        = optional(number, 50)
    vm_id            = number
    cpu              = number
    ram_dedicated    = number
    update           = optional(bool, false)
    igpu             = optional(bool, false)
  }))
}
