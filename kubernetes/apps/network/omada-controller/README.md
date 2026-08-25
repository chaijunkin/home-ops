# Omada-Controller

**Description:** TP-Link Omada SDN controller for managing EAP access points (dockerized).
**Category:** network

---

## Resources
- **Project Repository:** [Omada-Controller Source Code](https://github.com/mbentley/docker-omada-controller)
- **Helm/Manifest Source:** `Unknown`

---

## Related Links
- [Documentation](https://github.com/mbentley/docker-omada-controller#readme)
- [Application PRR Document](https://wiki.cloudjur.com/pages/tech/cloudjur/cloud-native/omada-controller)

## Notes
- **Currently not deployed**: manifests exist but `omada-controller/ks.yaml` is absent and the app is commented out of `network/kustomization.yaml`.
- When active, it exposes a LoadBalancer at `10.10.30.5` with full Omada port set (29810-29817, 27001/27002, 27017/27217) and NFS autobackup to `smb.cloudjur.com`.
