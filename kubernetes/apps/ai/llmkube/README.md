# LLMKube

Kubernetes operator ([defilantech/LLMKube](https://github.com/defilantech/LLMKube)) for
self-hosted llama.cpp inference. Strategy and naming follow
[joryirving/home-ops](https://github.com/joryirving/home-ops/blob/main/kubernetes/apps/base/llm/llmkube/README.md),
adapted for a **CPU-only single-node** cluster (`k8s-0`: no GPU).

A model is two CRs — a **`Model`** (weights source + hardware target) and an
**`InferenceService`** (serving pod: llama.cpp args, resources, probes,
endpoint). Following the upstream convention, model CRs live **in the folder of
the app that consumes them**, not under `llmkube/`.

## Naming convention (consumer-based)

Every `Model`/`InferenceService` is named after its **consumer + role**, never
after the underlying weights. Consumers only ever see these stable names, so
the model behind a role can change without touching client config:

| Role name        | Consumer | Weights                    | Served by            |
| ---------------- | -------- | -------------------------- | -------------------- |
| `memini-embed`   | memini   | Qwen3-Embedding-0.6B Q8_0  | LiteLLM → LM Studio¹ |
| `memini-rerank`  | memini   | Qwen3-Reranker-0.6B Q8_0   | llmkube (CPU)²       |
| `memini-summary` | memini   | Gemini 2.5 Flash Lite      | LiteLLM → Google     |

¹ LM Studio on `jk-mac-mini.cloudjur.com:1234` exposes `/v1/embeddings` but has
**no `/rerank` endpoint** (verified), so reranking cannot ride the Mac mini.
² CPU-only pod on `k8s-0`; idles to zero after 1h (`rolloutPolicy.waitForIdle`).

## Where things live

```
llmkube/                      # operator only (+ this README)
  ocirepository.yaml  helmrelease.yaml  ks.yaml

memini/app/models/            # memini's llama.cpp services, reconciled by the
  memini-rerank.yaml          #   memini Flux KS (active)
  memini-embed.yaml           #   fallback: enable here if LM Studio embed is down
memini/app/helmrelease.yaml   # consumer config — all three roles referenced by name
litellm/app/configmap.yaml    # `memini-embed` + `memini-summary` LiteLLM routes
```

There is no dedicated `llmkube-models` Kustomization; each consuming app's own
KS ships its models. The memini KS `dependsOn` the `llmkube` operator so the
CRDs exist first.

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
