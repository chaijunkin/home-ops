resource "proxmox_vm_qemu" "qemu_vm" {
  name        = var.vm_name
  vmid        = var.vmid
  target_node = var.target_node
  clone       = var.clone
  full_clone  = var.full_clone

  boot         = var.boot
  agent        = var.agent
  sockets      = var.sockets
  cores        = var.cores
  memory       = var.memory
  onboot       = var.onboot
  desc         = var.desc
  nameserver   = var.nameserver
  searchdomain = var.searchdomain
  tablet       = var.tablet
  balloon      = var.balloon
  numa         = var.numa
  vcpus        = var.vcpus
  cpu          = var.cpu
  pool         = var.pool
  tags         = var.tags
  hotplug      = var.hotplug

  # machine      = var.machine

  # dynamic "hostpci" {
  #   for_each = var.vm_hostpci
  #   content {
  #     host   = hostpci.value.host
  #     rombar = hostpci.value.rombar
  #     pcie   = hostpci.value.pcie 
  #   }
  # }

  dynamic "network" {
    for_each = var.vm_network
    content {
      model  = network.value.model
      bridge = network.value.bridge
      tag    = network.value.tag
    }
  }
  dynamic "disk" {
    for_each = var.vm_disk
    content {
      type    = disk.value.type
      storage = disk.value.storage
      size    = disk.value.size
      format  = disk.value.format
      ssd     = disk.value.ssd
    }
  }
  // Cloud Init Settings
  ipconfig0  = var.ipconfig0
  sshkeys    = var.ssh_public_keys
  ciuser     = var.default_image_username
  cipassword = var.default_image_password
  lifecycle {
    ignore_changes = [
      # Ignore changes to tags, e.g. because a management agent
      # updates these based on some ruleset managed elsewhere.
      desc,
    ]
  }
}

// Allow time for provisioning, initial boot, & cloud-init to complete before continuing.
// This is a rudimentary approach, but combined with Ansible wait_for port check, works for now. 
# resource "time_sleep" "wait_90_sec" {
#   depends_on      = [proxmox_vm_qemu.qemu_vm]
#   create_duration = "90s"
# }

//resource "time_sleep" "wait_90_sec" {
//  depends_on = [proxmox_vm_qemu.qemu_vm]
//  create_duration = "90s"
//}

// Post-provisioning pre-Ansible connectivity check before handoff to Ansible in parent module. 
// Default timeout of 5 minutes. 
//resource "null_resource" "provisioning" {
//  depends_on = [time_sleep.wait_90_sec]
//  provisioner "remote-exec" {

//    connection {
//      type            = var.provisioner_type
//      host            = var.ip_address
//      user            = var.default_image_username
//      password        = var.default_image_password
//      private_key     = var.private_key
//      target_platform = var.target_platform
// WINRM specific arguments:
//      https           = true
//      insecure        = true
//    }
//  }
//}

// Allow more time for cloudinit and possible reboot
//resource "time_sleep" "wait_90_sec_again" {
//  depends_on = [null_resource.provisioning]
//  create_duration = "90s"
//}
