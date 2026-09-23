
cat /etc/modprobe.d/zfs.conf 
options zfs zfs_arc_max=4294967296

## 1. Physical Disk Layout (Proxmox Node)
The underlying Proxmox hypervisor manages a tiered storage architecture comprising NVMe, SATA SSDs, and high-capacity HDDs:

- **OS / Boot Drive:**
  - `sdb`: 60GB Kingston SSD (LVM/EFI/BIOS Boot)

- **Fast Storage / Caching:**
  - `nvme0n1`: 1TB Samsung 970 EVO Plus NVMe (ZFS). *Note: High wearout (123%) and SMART failure warning.*
  - `sda`: 500GB Samsung 850 EVO SSD (ext4, mounted for backups/ISOs).

- **Bulk Storage (ZFS Pools):**
  - `sdc`, `sde`, `sdg`: 3x 28TB Seagate Exos HDDs (ZFS).
  - `sdd`, `sdf`: 2x 4TB Seagate IronWolf HDDs (ZFS).