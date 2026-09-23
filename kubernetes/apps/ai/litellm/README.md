# Litellm

**Description:** LLM gateway/proxy exposing an OpenAI-compatible API for 100+ model providers.
**Category:** ai

---

## Resources
- **Project Repository:** [Litellm Source Code](https://github.com/BerriAI/litellm)
- **Helm/Manifest Source:** `Unknown`

---

## Related Links
- [Documentation](https://docs.litellm.ai)
- [Application PRR Document](https://wiki.cloudjur.com/pages/tech/cloudjur/application/litellm)

## Notes
- Managed by [litellm-operator](https://github.com/home-operations/litellm-operator) via `LiteLLMProxy`, `LiteLLMModel` (per-model CRs in `app/models/`), and `applyMode: file`.
- Uses the database variant image `ghcr.io/berriai/litellm-database` backed by PostgreSQL (database pre-provisioned; no init container).
- Model config lives in `LiteLLMModel` resources; router/cache/metrics settings on the `LiteLLMProxy` spec.
- Exposes a separate admin dashboard route.
