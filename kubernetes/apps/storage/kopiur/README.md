# Kopiur

**Description:** VolSync backup orchestrator managing repository snapshots across the cluster.
**Category:** storage

---

## Resources
- **Project Repository:** [Kopiur Source Code](https://github.com/search?q=kopiur)
- **Helm/Manifest Source:** `oci://ghcr.io/home-operations/charts/kopiur`

---

## Related Links
- [Documentation]() <!-- Add link to upstream docs -->
- [Application PRR Document](https://wiki.cloudjur.com/pages/tech/cloudjur/cloud-native/kopiur)

## Notes
- Injected into apps via the reusable components in `kubernetes/components/kopiur/` (backup, remote, secret, temp-backup, adhoc-snapshot).
- Defines cluster-level backup repositories (e.g., `nas`) in `repository/`, with credentials from ExternalSecrets.
