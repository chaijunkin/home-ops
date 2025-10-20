talos_image = {
  # renovate: datasource=docker depName=ghcr.io/siderolabs/installer
  version        = "v1.10.6"
  # renovate: datasource=docker depName=ghcr.io/siderolabs/installer
  update_version = "v1.10.6"
  schematic_path = "talos/image/schematic.yaml"
  # Point this to a new schematic file to update the schematic
  # update_schematic_path = "talos/image/schematic.yaml"
  proxmox_datastore = "vm-store"
}
