// "Live" Terrafolocal.rm infra config for a nest k3s (k3s.io) cluster 
// running on Proxmox VMs. Post-provisioning config handed off to Ansible.

// Create k3s server node VM
module "k3sserver_vm" {
  source = "../modules/pve-vm"

  count = length(local.k3sserver_ip_addresses)

  target_node = local.k3sserver_target_node
  clone       = local.k3sserver_clone
  vm_name     = "${local.k3sserver_vm_name_prefix}${format("%02d", count.index + 1)}"
  vmid        = sum([300, count.index + 1])
  desc        = local.desc
  sockets     = local.vm_sockets
  cores       = local.k3sserver_vm_cores
  memory      = local.k3sserver_vm_memory
  vm_network  = local.k3sserver_vm_network
  vm_disk     = local.k3sserver_vm_disk
  onboot      = local.onboot
  full_clone  = local.full_clone

  nameserver             = local.nameserver
  searchdomain           = local.searchdomain
  boot                   = local.boot
  agent                  = local.agent
  ipconfig0              = "ip=${lookup(local.k3sserver_ip_addresses, count.index + 1)}${local.k3sserver_ip_cidr},gw=${local.k3sserver_gw}"
  ip_address             = lookup(local.k3sserver_ip_addresses, count.index + 1)
  ssh_public_keys        = local.ssh_public_keys
  default_image_username = local.default_image_username
  default_image_password = local.default_image_password
}

// Create k3s worker node VMs
module "k3sworker_nodes" {
  source = "../modules/pve-vm"

  count = length(local.k3sworker_ip_addresses)

  target_node = local.k3sworker_target_node
  clone       = local.k3sworker_clone
  vm_name     = "${local.k3sworker_vm_name_prefix}${format("%02d", count.index + 4)}"
  vmid        = sum([303, count.index + 1])
  desc        = local.desc
  sockets     = local.vm_sockets
  cores       = local.k3sworker_vm_cores
  memory      = local.k3sworker_vm_memory
  vm_network  = local.k3sworker_vm_network
  vm_disk     = local.k3sworker_vm_disk
  onboot      = local.onboot
  full_clone  = local.full_clone

  nameserver             = local.nameserver
  searchdomain           = local.searchdomain
  boot                   = local.boot
  agent                  = local.agent
  ipconfig0              = "ip=${lookup(local.k3sworker_ip_addresses, count.index + 1)}${local.k3sworker_ip_cidr},gw=${local.k3sworker_gw}"
  ip_address             = lookup(local.k3sworker_ip_addresses, count.index + 1)
  ssh_public_keys        = local.ssh_public_keys
  default_image_username = local.default_image_username
  default_image_password = local.default_image_password

}



/*

*/

// Ansible post-provisioning configuration
# resource "null_resource" "configuration" {
#   depends_on = [
#     module.k3sserver_vm,
#     module.k3sworker_nodes
#   ]

#   // Clear existing records (if exists) from known_hosts to prevent possible ssh connection issues
#   provisioner "local-exec" {
#     command = <<-EOT
#       if test -f "~/.ssh/known_hosts"; then
#         ssh-keygen -f ~/.ssh/known_hosts -R ${local.k3sserver_ip_address}
#       fi
#       EOT
#   }

#   # // Ansible playbook run - base config
#   # provisioner "local-exec" {
#   #   command = "ansible-playbook /etc/ansible/plays/k3s/install.yml"
#   # }
# }
