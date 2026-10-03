# Strix Halo (NixOS)

> **⚠️ TEMPORARY NODE**
> This bare-metal NixOS configuration hosts Qwen3.8-27B and ComfyUI directly via Podman because the main Talos cluster does not yet support GPU scheduling for these workloads.
>
> The services running on this host (`192.168.1.149`) are exposed and consumed by the `chaijunkin-home-ops` Talos cluster via ExternalName Services and LiteLLM Proxy routing.

The primary LLM engine is **Qwen3.8-27B** (via Gufo), served on port `8732` as the canonical model name `qwen3.8-27b`. Memini's blue Qwen3 embedding model and BGE reranker are served on ports 8743 and 8744; their green instances use ports 8745 and 8746. ComfyUI is available on port 8188.

Additional **Multiverse** inference services (ASR, TTS, Image, MiniMax-H3, DeepSeek-V4-Flash) are defined in `configuration.nix` as native Gufo systemd services and can be started on-demand via `systemctl start strix-halo-<model>.service`.

> **Future Goal:** Once GPU DRA is finalized in Talos, these models will migrate into Kubernetes as `LiteLLMModel` deployments and this node may be repurposed or adopted as a proper Talos worker.

## Deployment

```bash
task nixos:apply
```

Copies `configuration.nix`, `flake.nix`, `flake.lock`, and `secrets/secrets.sops.yaml` to `root@192.168.1.149:/etc/nixos/`, then runs `nixos-rebuild switch` remotely.

## Secrets Management (SOPS + age)

Secrets are managed by [sops-nix](https://github.com/Mic92/sops-nix). The encrypted file at `secrets/secrets.sops.yaml` is safe to commit — it is encrypted with two age recipients:

| Recipient | Key file | Purpose |
|---|---|---|
| `age1apaw0x3...` | `./age.key` (gitignored) | Master repo key — decrypt from your workstation |
| `age1kp83rqk...` | `./age2.key` (gitignored) | Strix Halo node key — decrypt at activation time |

The node key lives at `/var/lib/sops-age/keys.txt` on `192.168.1.149`. `sops-nix` decrypts secrets into `/run/secrets/` during system activation.

### Key management tasks

```bash
# Edit a secret (opens $EDITOR, re-encrypts on save)
task nixos:edit-secret FILE=infrastructure/nixos/strix-halo/secrets/secrets.sops.yaml

# Encrypt a plaintext secret file in-place
task nixos:encrypt-secret FILE=infrastructure/nixos/strix-halo/secrets/secrets.sops.yaml

# Backup the node's age private key to ./age2.key locally
task nixos:copy-key

# Rotate the node age key entirely (generates new key on node, copies locally, prints new pubkey)
task nixos:rotate-key
# → update .sops.yaml with the new public key, then:
# sops updatekeys --yes infrastructure/nixos/strix-halo/secrets/secrets.sops.yaml
# task nixos:apply
```

### Reprovisioning (node rebuilt from scratch)

If the node is wiped, the node key at `/var/lib/sops-age/keys.txt` is lost. To restore:

```bash
# Option A: Restore from local backup
ssh root@192.168.1.149 "mkdir -p /var/lib/sops-age && chmod 700 /var/lib/sops-age"
scp -i ~/.ssh/jk_inventory ./age2.key root@192.168.1.149:/var/lib/sops-age/keys.txt
ssh root@192.168.1.149 "chmod 600 /var/lib/sops-age/keys.txt"

# Option B: Generate a fresh key and rotate
task nixos:rotate-key
```

## Flake pins

The Gufo source and runtime image are pinned to the same upstream release in `flake.nix` and `configuration.nix`. Update both pins and regenerate `flake.lock` before deploying a new Gufo release.
