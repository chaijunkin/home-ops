talos_nodes = {
  "k8s-0" = {
    host_node    = "pve"
    machine_type = "controlplane"
    ip           = "10.10.30.31"
    network_devices = [
      {
        mac_address = "16:44:BB:A0:A4:28"
        tag         = 30
        ip_address  = "10.10.30.31"
        gateway     = "10.10.30.1"
      },
      {
        mac_address = "16:44:BB:A0:A4:29"
        tag         = 31
        ip_address  = "10.10.31.254"
        # gateway     = "10.10.31.1"
      },
      {
        mac_address = "16:44:BB:A0:A4:30"
        tag         = 32
        ip_address  = "10.10.32.254"
        # gateway     = "10.10.32.1"
      },
      {
        mac_address = "16:44:BB:A0:A4:31"
        tag         = 33
        ip_address  = "10.10.33.254"
        # gateway     = "10.10.33.1"
      },
      {
        mac_address = "16:44:BB:A0:A4:32"
        tag         = 10
        ip_address  = "10.10.10.254"
        # gateway     = "10.10.10.1"
      }
      ,
      {
        mac_address = "16:44:BB:A0:A4:33"
        tag         = 27
        ip_address  = "10.10.27.254"
      },
    ]

    vm_id         = 3031
    cpu           = 9
    ram_dedicated = 51200
    igpu          = true
    dns           = ["10.10.30.1"]
    dns_domain    = "cloudjur.com"
    datastore_id  = "fast"
    disks = [
      {
        datastore_id = "fast"
        interface    = "scsi0"
        iothread     = true
        cache        = "writethrough"
        discard      = "on"
        ssd          = true
        file_format  = "raw"
        size         = 850
        # file_id will be set in the Terraform code, not here
      },
      {
        datastore_id = "vm-store"
        interface    = "scsi1"
        iothread     = true
        cache        = "writethrough"
        discard      = "on"
        ssd          = true
        file_format  = "raw"
        size         = 400
        # file_id will be set in the Terraform code, not here
      }
      # Add more disks here as needed
    ]
  }
}
