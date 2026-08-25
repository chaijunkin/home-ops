# Litellm-Operator

**Description:** Kubernetes-native operator managing LiteLLM proxy deployments via `LiteLLMProxy`, `LiteLLMModel`, `LiteLLMVirtualKey`, and `LiteLLMMCPServer` CRDs.
**Category:** ai

---

## Resources
- **Project Repository:** [Litellm-Operator Source Code](https://github.com/home-operations/litellm-operator)
- **Helm/Manifest Source:** `oci://ghcr.io/home-operations/charts/litellm-operator`

---

## Related Links
- [Documentation](https://github.com/home-operations/litellm-operator#readme)
- [Application PRR Document](https://wiki.cloudjur.com/pages/tech/cloudjur/application/litellm-operator)

## Notes
- Deploys the CRDs consumed by the [litellm](../litellm) app (`LiteLLMProxy`, `LiteLLMModel`).
- Webhook enabled with `install/upgrade.crds: CreateReplace`; `llmkube.autoRegister: true`.
- The `litellm` Kustomization `dependsOn` this one, so models/proxy only apply after the operator is healthy.
