# Strix Halo (NixOS)

> **⚠️ TEMPORARY NODE**
> This bare-metal NixOS configuration is temporarily used to host heavy LLM and image generation models (ComfyUI, Qwen, Gemma, Nemotron, Whisper, Lemonade-TTS) directly via Podman because the main Talos cluster does not yet support GPU scheduling for these workloads.
> 
> The services running on this host (`192.168.1.149`) are exposed and consumed by the `chaijunkin-home-ops` Talos cluster via ExternalName Services and Litellm Proxy routing.
> 
> **Future Goal:** Once GPU provisioning (e.g. `llama-strix-gpu` DRA) is finalized in Talos, these models will be migrated into the Kubernetes cluster natively as `LiteLLMModel` and `comfyui` deployments, and this node may be repurposed or adopted as a proper Talos worker.

## Deployment

To deploy this configuration to the host:

```bash
# Push config and trigger a rebuild
scp -r * root@192.168.1.149:/etc/nixos/
ssh root@192.168.1.149 "cd /etc/nixos && nixos-rebuild switch --flake .#strix-halo"
```
