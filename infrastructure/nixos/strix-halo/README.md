# Strix Halo (NixOS)

> **⚠️ TEMPORARY NODE**
> This bare-metal NixOS configuration hosts Qwen3.8 Flash-Next and ComfyUI directly via Podman because the main Talos cluster does not yet support GPU scheduling for these workloads. Both services share the GPU and may contend for memory during image generation.
> 
> The services running on this host (`192.168.1.149`) are exposed and consumed by the `chaijunkin-home-ops` Talos cluster via ExternalName Services and Litellm Proxy routing.

Qwen3.8 Flash-Next serves the canonical model name `qwen3.8-flash-next` on port
8732. ComfyUI is available on port 8188. The ComfyUI data directory is
`/var/lib/comfyui-data`; add compatible checkpoints and other model files under
its `models/` subdirectories before queuing image-generation workflows.
> 
> **Future Goal:** Once GPU provisioning (e.g. `llama-strix-gpu` DRA) is finalized in Talos, these models will be migrated into the Kubernetes cluster natively as `LiteLLMModel` and `comfyui` deployments, and this node may be repurposed or adopted as a proper Talos worker.

## Deployment

To deploy this configuration to the host:

```bash
# Copy changed NixOS files and activate the flake
scp configuration.nix flake.nix flake.lock root@192.168.1.149:/etc/nixos/
ssh root@192.168.1.149 "nixos-rebuild switch --flake /etc/nixos#strix-halo"
```
