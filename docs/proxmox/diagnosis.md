# Proxmox iGPU GVT-g Host Diagnosis Report

*   **Date of Diagnosis:** 2026-08-25
*   **Host Node IP:** `10.10.30.10` (`pve`)
*   **Hardware CPU:** Intel Xeon E-2246G (Coffee Lake UHD Graphics P630)

---

## 1. Bootloader & Kernel Configuration

*   **Bootloader:** GRUB (Legacy BIOS boot partition config, `/etc/default/grub`).
*   **Active Kernel Command Line:**
    ```bash
    BOOT_IMAGE=/vmlinuz-6.17.13-2-pve root=/dev/mapper/pve-root ro quiet intel_iommu=on iommu=pt i915.enable_gvt=1 drm.debug=0
    ```
    *   `intel_iommu=on`: Enables IOMMU for host PCIe addressing.
    *   `iommu=pt`: Enables pass-through mode for IOMMU translation.
    *   `i915.enable_gvt=1`: Natively enables Intel GVT-g vGPU sharing on the kernel Intel graphics module.

---

## 2. Kernel Modules Status

The following modules are successfully loaded and active:
*   `i915`: Loaded and in use by `kvmgt`.
*   `kvmgt`: Active (GVT-g kernel virtualization module).
*   `mdev`: Active (Mediated device driver backend).
*   `vfio` / `vfio_pci`: Active.

---

## 3. Host Active GVT-g vGPU Profiles

The Coffee Lake UHD Graphics P630 GPU has successfully generated the following GVT-g vGPU profiles under `/sys/bus/pci/devices/0000:00:02.0/mdev_supported_types/`:

### Profile: `i915-GVTg_V5_4`
*   **Low GM Size (VRAM):** 128MB
*   **High GM Size:** 512MB
*   **Max Resolution:** `1920x1200`
*   **Weight (Priority):** 4
*   **Available Host Instances:** **1**

### Profile: `i915-GVTg_V5_8`
*   **Low GM Size (VRAM):** 64MB
*   **High GM Size:** 384MB
*   **Max Resolution:** `1024x768`
*   **Weight (Priority):** 2
*   **Available Host Instances:** **2** (Perfect for splitting between k8s and NAS VMs)
