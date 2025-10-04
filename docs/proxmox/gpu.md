Source: https://3os.org/infrastructure/proxmox/gpu-passthrough/igpu-passthrough-to-vm/#introduction
Source: https://www.reddit.com/r/homelab/comments/jyudnn/enable_mediated_intel_igpu_gvtg_for_vms_in/
Source: https://perfectmediaserver.com/05-advanced/passthrough-igpu-gvtg/#setting-up-pci-passthrough-on-proxmox

Source: https://www.reddit.com/r/immich/comments/18av44a/proxmox_hardware_acceleration_uhd_graphics_630/ (THIS WORKS)

```
as you are using VM not LXC, you need GPU passthrough, you can get information from https://www.reddit.com/r/homelab/comments/b5xpua/the_ultimate_beginners_guide_to_gpu_passthrough/ and https://pve.proxmox.com/wiki/PCI(e)_Passthrough .

Once you have done, you should be able to run intel_gpu_top on DebianVM. for docker/immich setup, it is simple you just need modify hwaccel.yml passing /dev/dri into the container, refer to https://immich.app/docs/features/hardware-transcoding

I'm running the similar setup with Proxmox->DebianLCX->Docker->Immich without any problem. you can validate your setup by run intel_gpu_top from package intel-gpu-tools
```

```


Ok, for any one who stumble on this post with this same problem. Here is the solution i have found and it worked for me.
If you are using ext4 file system with EFI so you are using GRUB please try the following and let me know if it works for you.

To check which partition is /boot with vfat format:

:\~# lsblk -o +FSTYPE

To initialize ESP sync first unmount boot partition:

:\~# umount /boot/efi

Then link the vfat partiton with proxmox-boot-tool:

:\~# proxmox-boot-tool init /dev/XXXXXXXX where XXXXXXXX is the name of vfat partiton from lsblk +FSYSTEM

Then:

:\~# mount -a

Then to update modules:

:\~# update-initramfs -u -k all

Reboot
```

I have similar issue as above, where
`No /etc/kernel/proxmox-boot-uuids found, skipping ESP sync.`

https://www.reddit.com/r/Proxmox/comments/1agjbvu/updateinitramfs_u_k_all_problem/
