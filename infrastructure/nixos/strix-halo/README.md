# Strix Halo (NixOS)

> **⚠️ TEMPORARY NODE**
> This bare-metal NixOS configuration hosts Qwen3.8 Flash-Next and ComfyUI directly via Podman because the main Talos cluster does not yet support GPU scheduling for these workloads. Both services share the GPU and may contend for memory during image generation.
> 
> The services running on this host (`192.168.1.149`) are exposed and consumed by the `chaijunkin-home-ops` Talos cluster via ExternalName Services and Litellm Proxy routing.

Qwen3.8 Flash-Next serves the canonical model name `qwen3.8-flash-next` on port
8732. Memini's blue Qwen3 embedding model and BGE reranker are served on ports
8743 and 8744; their green instances use ports 8745 and 8746. ComfyUI is
available on port 8188. The ComfyUI data directory is
`/var/lib/comfyui-data`; add compatible checkpoints and other model files under
its `models/` subdirectories before queuing image-generation workflows.

The green instances use the same model files and aliases as blue. For a
blue/green rollout, start and validate green, then update the existing LiteLLM
model resources to point to ports 8745 and 8746. Once Flux reconciles that
GitOps change, blue remains available on ports 8743 and 8744 for rollback.
Switching to a different embedding model requires a re-embedding plan for
stored vectors; this same-model rollout does not.
> 
> **Future Goal:** Once GPU provisioning (e.g. `llama-strix-gpu` DRA) is finalized in Talos, these models will be migrated into the Kubernetes cluster natively as `LiteLLMModel` and `comfyui` deployments, and this node may be repurposed or adopted as a proper Talos worker.

## Deployment

Deploy the flake and activate it on Strix Halo with the repository Taskfile:

```bash
task nixos:apply
```

The task defaults to `root@192.168.1.149` and `~/.ssh/jk_inventory`. Override
`STRIX_HOST`, `STRIX_USER`, or `STRIX_SSH_KEY` when running it against a
different target or with a different SSH identity.

The Gufo source and runtime image are pinned to the same upstream release in
`flake.nix` and `configuration.nix`; update both pins and regenerate
`flake.lock` before deploying a Gufo release.
