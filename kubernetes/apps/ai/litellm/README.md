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

The `self-hosted`, `auto`, and `qwen3.8-flash-next` model aliases are routed to
the Gufo OpenAI-compatible server on the Strix Halo mini PC at
`192.168.1.149:8732`, serving `qwen3.8-flash-next`. `auto` keeps the
complexity-router interface, with all tiers and the classifier routed to this
self-hosted model. There are no cloud fallbacks. The single `self-hosted` alias
supports both vision and function tools. Clients using MCP tools must use Chat
Completions because Gufo's `/v1/responses` endpoint does not support tools.
Hardware: FAEX1, AMD Ryzen AI Max+ 395 with integrated Radeon 8060S, 128GB RAM,
1.8TB NVMe, running NixOS. Gufo is configured with a 131,072-token context and
one session. ComfyUI also runs on this host; both services share the GPU and
may contend for memory during image generation.

## Strix Halo telemetry

The Strix Halo host is monitored through two Prometheus endpoints:

- `192.168.1.149:8732/metrics` — Gufo request, token, prefill/decode, and GPU metrics.
- `192.168.1.149:9100/metrics` — NixOS node and AMDGPU sysfs metrics.

The host uses the `strix-halo` node label and the Gufo endpoint uses
`service=gufo`, `namespace=llm`, and `job=gufo`. The ROCm dashboard's
service selector is label-based so it works for this native Podman service as
well as Kubernetes-hosted llama.cpp services.
