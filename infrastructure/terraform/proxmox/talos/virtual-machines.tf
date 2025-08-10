resource "proxmox_virtual_environment_vm" "this" {
  for_each = var.nodes

  node_name = each.value.host_node

  name        = each.key
  description = each.value.machine_type == "controlplane" ? "Talos Control Plane" : "Talos Worker"
  tags        = each.value.machine_type == "controlplane" ? ["k8s", "control-plane"] : ["k8s", "worker"]
  on_boot     = true
  vm_id       = each.value.vm_id

  machine       = "q35"
  scsi_hardware = "virtio-scsi-single"
  bios          = "seabios"

  agent {
    enabled = true
  }

  cpu {
    cores = each.value.cpu
    type  = "host"
  }

  memory {
    dedicated = each.value.ram_dedicated
  }

  dynamic "network_device" {
    for_each = each.value.network_devices
    content {
      bridge      = "vmbr0"
      mac_address = network_device.value.mac_address
      vlan_id     = network_device.value.tag
    }
  }
  # Example: Add a second

  disk {
    datastore_id = each.value.datastore_id
    interface    = "scsi0"
    iothread     = each.value.disk_iothread
    cache        = each.value.disk_cache
    discard      = each.value.disk_discard
    ssd          = each.value.disk_ssd
    file_format  = each.value.disk_file_format
    size         = each.value.disk_size
    file_id      = proxmox_virtual_environment_download_file.this["${each.value.host_node}_${each.value.update == true ? local.update_image_id : local.image_id}"].id
  }

  boot_order = ["scsi0"]

  operating_system {
    type = "l26" # Linux Kernel 2.6 - 6.X.
  }

  initialization {
    datastore_id = each.value.datastore_id

    # Optional DNS Block
    dns {
      domain  = each.value.dns_domain
      servers = each.value.dns
    }

    dynamic "ip_config" {
      for_each = each.value.network_devices
      content {
        ipv4 {
          # Use device-specific IP if provided, otherwise fall back to primary IP for first device or DHCP
          address = ip_config.value.ip_address != null ? "${ip_config.value.ip_address}/${var.cluster.subnet_mask}" : (ip_config.key == 0 ? "${each.value.ip}/${var.cluster.subnet_mask}" : "dhcp")
          # Use device-specific gateway if provided, otherwise fall back to cluster gateway for first device only
          gateway = ip_config.value.gateway != null ? ip_config.value.gateway : (ip_config.key == 0 ? var.cluster.gateway : null)
        }
      }
    }
  }

  dynamic "hostpci" {
    for_each = each.value.igpu ? [1] : []
    content {
      # Passthrough iGPU
      ### VIRTUAL
      device = "hostpci0"
      id     = "0000:00:02.0"
      rombar = true
      pcie   = false
      # ### PHYSICAL
      # device  = "hostpci0"
      # mapping = "iGPU"
      # pcie    = true
      # rombar  = true
      # xvga    = false
    }
  }
}
