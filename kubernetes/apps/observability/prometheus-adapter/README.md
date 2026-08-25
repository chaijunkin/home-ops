# Prometheus-Adapter

**Description:** Converts Prometheus metrics into the Kubernetes custom metrics API for autoscaling.
**Category:** observability

---

## Resources
- **Project Repository:** [Prometheus-Adapter Source Code](https://github.com/kubernetes-sigs/prometheus-adapter)
- **Helm/Manifest Source:** `oci://ghcr.io/prometheus-community/charts/prometheus-adapter`

---

## Related Links
- [Documentation](https://github.com/kubernetes-sigs/prometheus-adapter#readme)
- [Application PRR Document](https://wiki.cloudjur.com/pages/tech/cloudjur/cloud-native/prometheus-adapter)

## Notes
- Consumes `kube-prometheus-stack` metrics; enables HPA scaling on custom metrics.
