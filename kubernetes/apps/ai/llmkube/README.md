# LLMKube

Kubernetes operator ([defilantech/LLMKube](https://github.com/defilantech/LLMKube)) for
self-hosted llama.cpp inference. Strategy and naming follow
[joryirving/home-ops](https://github.com/joryirving/home-ops/blob/main/kubernetes/apps/base/llm/llmkube/README.md),
adapted for a **CPU-only single-node** cluster (`k8s-0`: no GPU).

A model is two CRs — a **`Model`** (weights source + hardware target) and an
**`InferenceService`** (serving pod: llama.cpp args, resources, probes,
endpoint). Following the upstream convention, model CRs live **in the folder of
the app that consumes them**, not under `llmkube/`.

## Naming convention

LiteLLM fronts every role; consumers only ever see LiteLLM model names.
Memini's primary embedding and reranking backends run on Strix Halo. The old
llmkube manifests remain available for rollback but are excluded from Memini's
Kustomization. LM Studio carries the `lmstudio-*` prefix as a secondary route:

| LiteLLM route     | Backend                                   | Weights                   |
| ----------------- | ----------------------------------------- | ------------------------- |
| `memini-embed`    | Strix Halo `memini-embeddings` (GPU)      | Qwen3-Embedding-0.6B Q8_0 |
| `memini-rerank`   | Strix Halo `memini-reranker` (GPU)        | BGE-Reranker-v2-M3 Q8_0   |
| `lmstudio-embed`  | LM Studio on jk-mac-mini (secondary)      | same embedding weights    |
| `memini-summary`  | Gemini 2.5 Flash Lite (cloud)             | —                         |

Reranking rides LiteLLM's `infinity/` provider, which speaks the
Cohere-compatible `/rerank` protocol that llama.cpp serves. LM Studio has no
`/rerank` endpoint at all (verified), so ranking has no lmstudio route.

Consumers reference only these stable names, so the model behind a role can
change without touching client config. This layout is also what the future
litellm-operator migration expects.

## Where things live

```
llmkube/                      # operator only (+ this README)
  ocirepository.yaml  helmrelease.yaml  ks.yaml

memini/app/models/            # memini's llama.cpp services, reconciled by the
  memini-rerank.yaml          #   rollback manifests (not in the active Kustomization)
  memini-embed.yaml
memini/app/helmrelease.yaml   # consumer config — all three roles referenced by name
litellm/app/models/           # `memini-*` LiteLLM routes
```

There is no dedicated `llmkube-models` Kustomization; each consuming app's own
KS ships its models. Memini no longer depends on the llmkube operator for its
embedding and reranking services.

## CPU-only adaptations

- `hardware.accelerator: cpu` (the CRD default) — no `gpu:` block, no
  ResourceClaimTemplate, no oneAPI/Vulkan env vars.
- Standard `ghcr.io/ggml-org/llama.cpp:server` image (digest-pinned), not the
  Vulkan build.
- Threads sized for the shared node (`6`/`6`) with `cpu: "2"` requests; bump
  only if k8s-0 gains capacity.
- `--kv-unified` on the reranker keeps the KV cache in RAM for the small
  context windows used by ranking.

## Adding a new model

1. Drop `<consumer>-<role>.yaml` (Model + InferenceService pair) into the
   consuming app's `models/` directory.
2. Add it to that app's `app/kustomization.yaml`.
3. Reference it by role name from the app's config (env var / api_base).
4. If the role should instead ride LiteLLM/LM Studio, add a `model_name`
   entry in litellm's configmap and skip step 2 entirely.

Weights are pulled via `hf://` sources on first reconcile; there is no shared
cache PVC yet, so restarts re-download unless you add a `modelCache` claim.
