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

## Temporary self-hosted backend

The `self-hosted` model alias is temporarily routed to the Halogen OpenAI-compatible
server on the Strix Halo mini PC at `192.168.1.149:8731`, serving
`qwen38-flash-next`. This preserves the existing OpenClaw and Hermes model name
while testing the new hardware.

Hardware: FAEX1, AMD Ryzen AI Max+ 395 with integrated Radeon 8060S, 128GB RAM,
1.8TB NVMe, running NixOS. Halogen is configured with a 16,384-token working
limit and a 262,144-position KV pool. This backend is temporary; restore the
`jk-mac-mini` LM Studio endpoint in `app/models/self-hosted.yaml` when testing
is complete.
