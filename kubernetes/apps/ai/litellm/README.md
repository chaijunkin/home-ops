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

The canonical `qwen3.8-flash-next` LiteLLM model group routes to the Gufo
OpenAI-compatible server on Strix Halo at `192.168.1.149:8732`. LiteLLM uses
the `hosted_vllm` provider to translate Anthropic Messages requests to Chat
Completions rather than Gufo's unsupported Responses API. The `self-hosted`
client name is a LiteLLM router alias for `qwen3.8-flash-next`; both names use
the same model configuration and upstream. Responses and model discovery may
identify the canonical name rather than `self-hosted`.

`auto` keeps the complexity-router interface, with its classifier and tiers
routed through their configured model groups. There are no cloud fallbacks.
The canonical model supports both vision and function tools. Clients using MCP
tools must use Chat Completions because Gufo's `/v1/responses` endpoint does
not support tools.
Hardware: FAEX1, AMD Ryzen AI Max+ 395 with integrated Radeon 8060S, 128GB RAM,
1.8TB NVMe, running NixOS. Gufo is configured with a 131,072-token context and
one session. ComfyUI also runs on this host; both services share the GPU and
may contend for memory during image generation.

## ToolHive MCP connectors

LiteLLM registers one remote `LiteLLMMCPServer` connector for each active
ToolHive MCPServer. These point to ToolHive's existing in-cluster proxy
Services; LiteLLM does not create or own duplicate MCP workloads. Open WebUI
can connect to the individual LiteLLM MCP server endpoints to keep each
application's tool catalog separate. Enabling multiple connections at once
still combines their tools in a completion request and can exceed Gufo's
128-function limit.

Do not register the ToolHive `VirtualMCPServer` proxies (`vmcp-mcp-*`) as
`LiteLLMMCPServer` connectors. The optimizer gateway exposes only
`find_tool`/`call_tool`, but LiteLLM expands every backend tool it discovers
through them, which reliably exceeds the limit above.

## Strix Halo telemetry

The Strix Halo host is monitored through two Prometheus endpoints:

- `192.168.1.149:8732/metrics` — Gufo request, token, prefill/decode, and GPU metrics.
- `192.168.1.149:9100/metrics` — NixOS node and AMDGPU sysfs metrics.

The host uses the `strix-halo` node label and the Gufo endpoint uses
`service=gufo`, `namespace=llm`, and `job=gufo`. The ROCm dashboard's
service selector is label-based so it works for this native Podman service as
well as Kubernetes-hosted llama.cpp services.

Memini's `embed` and `memini-rerank` LiteLLM routes connect directly to
the Strix Halo llama.cpp services at `192.168.1.149:8743` and
`192.168.1.149:8744`. The embedding model returns 1024-dimensional vectors,
matching Memini's configured `MEMINI_EMBED_DIMS`.
