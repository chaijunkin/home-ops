talos_nodes = {
  "k8s-0" = {
    host_node    = "dashy"
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
    ]

    vm_id         = 601
    cpu           = 9
    ram_dedicated = 40960
    igpu          = false
    dns           = ["10.10.30.1"]
    dns_domain    = "cloudjur.com"
  }
}
