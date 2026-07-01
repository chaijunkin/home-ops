# Proxmox Host Setup for Intel iGPU Passthrough

To properly pass the Intel iGPU (like the UHD Graphics P630 on your E-2246G) to a Talos VM, you must ensure the Proxmox host itself does not seize control of the GPU display buffer, and that the IOMMU groups are correctly isolated.

Run these steps as `root` directly on your Proxmox server (`pve`).

## 1. Enable IOMMU and Prevent Host Display Initialization

You need to pass the `intel_iommu=on`, `iommu=pt`, and `i915.enable_display=0` arguments to the kernel on boot.

Depending on whether your Proxmox was installed via Legacy BIOS (GRUB) or UEFI (systemd-boot), the file you edit changes. (Proxmox 8.x defaults to systemd-boot for ZFS/UEFI installs).

**For systemd-boot (UEFI):**
Edit `/etc/kernel/cmdline` and ensure it looks like this:
```bash
root=ZFS=rpool/ROOT/pve-1 boot=zfs intel_iommu=on iommu=pt i915.enable_display=0
```

**For GRUB (Legacy BIOS):**
Edit `/etc/default/grub` and append to `GRUB_CMDLINE_LINUX_DEFAULT`:
```bash
GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt i915.enable_display=0"
```

## 2. Apply the Bootloader Changes

Run the Proxmox boot tool to apply the changes to whichever bootloader your system uses:
```bash
proxmox-boot-tool refresh
```
*(If you are exclusively using GRUB, you can also run `update-grub`).*

## 3. Load VFIO Kernel Modules

The host needs the VFIO modules loaded to bind the PCI device and pass it through to the VM.
Add the following lines to `/etc/modules`:

```bash
cat <<EOF >> /etc/modules
vfio
vfio_iommu_type1
vfio_pci
vfio_virqfd
EOF
```

## 4. Blacklist Default Drivers (Optional but Recommended)

To ensure Proxmox doesn't try to use the iGPU for a local console (which we already disabled via `i915.enable_display=0`, but this is a good failsafe), you can blacklist the drivers:

```bash
echo "blacklist radeon" >> /etc/modprobe.d/blacklist.conf
echo "blacklist nouveau" >> /etc/modprobe.d/blacklist.conf
echo "blacklist nvidia" >> /etc/modprobe.d/blacklist.conf
# We don't strictly blacklist i915 because we might need it for GVT-g/MDEV if we split the GPU later, 
# but for raw passthrough, the boot arguments above are sufficient.
```

## 5. Update Initramfs and Reboot

Apply all module changes to the initial ramdisk and reboot the host:

```bash
update-initramfs -u -k all
reboot
```

---

## 6. Verification (Post-Reboot)

Once Proxmox is back online, verify IOMMU is enabled:
```bash
dmesg | grep -e DMAR -e IOMMU
```
You should see output confirming `IOMMU enabled`.

Check that the VFIO modules are loaded:
```bash
lsmod | grep vfio
```

You are now ready to pass `hostpci0` into the Talos VM!

Random docs: https://github.com/fire1ce/3os.org/discussions/70