locals {

  # -- Common Variables -- #
  desc                   = "k3s VM, created with Terraform on ${timestamp()}"
  full_clone             = true
  default_image_username = var.default_image_username
  default_image_password = var.default_image_password
  nameserver             = var.nameserver
  searchdomain           = var.searchdomain

  onboot     = true
  boot       = "order=scsi0;ide2;net0"
  agent      = 1
  vm_sockets = 1
  hotplug    = "network,disk,cpu,memory,usb"
  numa       = true

  # -- k3s Server Node VM Variables -- #
  k3sserver_target_node    = var.k3sserver_target_node
  k3sserver_clone          = var.k3sserver_clone
  k3sserver_vm_name_prefix = var.k3sserver_vm_name_prefix
  k3sserver_vm_cores       = var.k3sserver_vm_cores
  k3sserver_vm_memory      = var.k3sserver_vm_memory
  k3sserver_ip_addresses   = var.k3sserver_ip_addresses
  k3sserver_ip_cidr        = "/24"
  k3sserver_gw             = var.k3sserver_gw
  // Dynamic block for network adapters to add to VM
  k3sserver_vm_network = var.k3sserver_vm_network

  // Dynamic block for disk devices to add to VM. 1st is OS, size should match or exceed template.
  k3sserver_vm_disk = var.k3sserver_vm_disk

  # -- k3s Worker Node VM Variables -- #
  k3sworker_target_node    = var.k3sworker_target_node
  k3sworker_clone          = var.k3sworker_clone
  k3sworker_vm_name_prefix = var.k3sworker_vm_name_prefix
  k3sworker_vm_memory      = var.k3sworker_vm_memory
  k3sworker_vm_cores       = var.k3sworker_vm_cores
  // IP assignment count in this block will control count of k3sworker VMs provisioned
  k3sworker_ip_addresses = var.k3sworker_ip_addresses
  k3sworker_ip_cidr      = var.k3sworker_ip_cidr
  k3sworker_gw           = var.k3sworker_gw
  // Dynamic block for network adapters to add to VM
  k3sworker_vm_network = var.k3sworker_vm_network

  // Dynamic block for disk devices to add to VM. 1st is OS, size should match or exceed template.
  k3sworker_vm_disk = var.k3sworker_vm_disk

  ssh_public_keys = var.ssh_public_keys
}

