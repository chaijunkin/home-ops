# /etc/network/interfaces

auto lo
iface lo inet loopback

auto eno1
iface eno1 inet manual
  post-up ethtool -K eno1 tso off gso off

auto enp8s0
iface enp8s0 inet manual
  post-up ethtool -K enp8s0 tso off gso off

auto vlan30
iface vlan30 inet static
        address 10.10.30.10/24
        gateway 10.10.30.1
        ovs_type OVSIntPort
        ovs_bridge vmbr0
        ovs_options tag=30

auto vlan0
iface vlan0 inet static
        address 192.168.1.10/24
        ovs_type OVSIntPort
        ovs_bridge vmbr0

auto bond0
iface bond0 inet manual
        ovs_bonds eno1 enp8s0
        ovs_type OVSBond
        ovs_bridge vmbr0
        ovs_options bond_mode=active-backup

auto vmbr0
iface vmbr0 inet manual
        ovs_type OVSBridge
        ovs_ports bond0 vlan30 vlan0

source /etc/network/interfaces.d/*