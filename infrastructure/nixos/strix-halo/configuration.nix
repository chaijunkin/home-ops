{ config, pkgs, lib, gufo, ... }:

{
  imports = [
    ./hardware-configuration.nix
  ];

  networking.hostName = "strix-halo";

  # Disk layout (nixos-anywhere requires disko for automated partitioning)
  # NOTE: We are using a very basic single-ext4 partition scheme for your single drive.
  disko.devices = {
    disk = {
      main = {
        type = "disk";
        device = "/dev/nvme0n1"; # Adjust if your drive name is different
        content = {
          type = "gpt";
          partitions = {
            boot = {
              size = "1M";
              type = "EF02"; # for grub MBR
            };
            ESP = {
              size = "512M";
              type = "EF00";
              content = {
                type = "filesystem";
                format = "vfat";
                mountpoint = "/boot";
              };
            };
            root = {
              size = "100%";
              content = {
                type = "filesystem";
                format = "ext4";
                mountpoint = "/";
              };
            };
          };
        };
      };
    };
  };

  # Use the systemd-boot EFI boot loader.
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  # --- STRIX HALO VRAM HACKS ---
  # These kernel arguments force the AMD APU to pin UMA memory as dedicated VRAM for AI workloads.
  boot.kernelParams = [
    "amd_iommu=off"
    "amdgpu.gttsize=126976"
    "mitigations=off"
    "ttm.pages_limit=32505856"
    "amdgpu.vm_update_mode=0"
    "amdgpu.noretry=0"
    "amdgpu.sg_display=0"
  ];

  # Upgrade to the absolute latest Linux kernel for Strix Halo / RDNA 3.5 support
  boot.kernelPackages = pkgs.linuxPackages_latest;
  hardware.enableRedistributableFirmware = true;

  # Enable the OpenSSH daemon.
  services.openssh.enable = true;

  services.prometheus.exporters.node = {
    enable = true;
    enabledCollectors = [ "hwmon" ];
    listenAddress = "0.0.0.0";
    port = 9100;
  };

  networking.firewall.allowedTCPPorts = [ 9100 8081 8188 8732 8737 ];
  
  # Ensure your personal SSH key is authorized so you can log in after installation!
  users.users.root.openssh.authorizedKeys.keys = [
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDhjmuxHcocxOOqj1bnhxsS0WFEhfChQccmdyIISTt4kw2kGFIbm9jzrcEsOr+ZdvLaBErWgWy3k8tkU3SBLKos4Bi35NGTjupvL60vADo6nxj15UYcohhS4JO3ggUiVkCXlQKmtHtdIYeIYTsU32pcHoMXVq7UMzPyVplMy2cpJLOJe0vEu/gm+Wq79KGgshnWL1RAgUgfp6aNEsmmFeyL+zJ0jCpjMdNphx8yo+1Kjh07gRi1jcOoeBO7SwGqotySVXd8kYj+qREQc7QeXFTg/Gy1fMct+htdBPy2lCc/ftS9qRCi1ADd55KCJmUUpt1x3W+5xFUWlSZlJwqNeGgopXkjN5O3l9Nr5vrPj/NjMK5FXR2ljsAgkf/mY912CDdxlcvSvYHkyJky0l40/DGVvFCbMJ9vP7c7oDuNn4Bcp+1LG8Y1t9i2YS2L4qJVstFKsM+6aCdYDIu2Ed1B9oH72fyPfige1BGmBjUntBWdhw1pxwmGo2baFfNJEzi6eh8= icybu@LAPTOP-P75UTKU6"
  ];

  # Define the standard user account
  users.users.nixos = {
    isNormalUser = true;
    extraGroups = [ "wheel" ]; # Enable 'sudo' for the user
    openssh.authorizedKeys.keys = [
      "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDhjmuxHcocxOOqj1bnhxsS0WFEhfChQccmdyIISTt4kw2kGFIbm9jzrcEsOr+ZdvLaBErWgWy3k8tkU3SBLKos4Bi35NGTjupvL60vADo6nxj15UYcohhS4JO3ggUiVkCXlQKmtHtdIYeIYTsU32pcHoMXVq7UMzPyVplMy2cpJLOJe0vEu/gm+Wq79KGgshnWL1RAgUgfp6aNEsmmFeyL+zJ0jCpjMdNphx8yo+1Kjh07gRi1jcOoeBO7SwGqotySVXd8kYj+qREQc7QeXFTg/Gy1fMct+htdBPy2lCc/ftS9qRCi1ADd55KCJmUUpt1x3W+5xFUWlSZlJwqNeGgopXkjN5O3l9Nr5vrPj/NjMK5FXR2ljsAgkf/mY912CDdxlcvSvYHkyJky0l40/DGVvFCbMJ9vP7c7oDuNn4Bcp+1LG8Y1t9i2YS2L4qJVstFKsM+6aCdYDIu2Ed1B9oH72fyPfige1BGmBjUntBWdhw1pxwmGo2baFfNJEzi6eh8= icybu@LAPTOP-P75UTKU6"
    ];
  };
  system.stateVersion = "25.05";

  # --- ESSENTIAL SYSTEM PACKAGES ---
  environment.systemPackages = with pkgs; [
    # Hardware & GPU Telemetry
    lshw
    pciutils
    usbutils
    dmidecode
    smartmontools
    nvme-cli
    lm_sensors
    nvtopPackages.amd
    amdgpu_top

    # Process & Resource Monitoring
    btop
    htop
    iotop

    # Networking & Diagnostics
    curl
    wget
    git
    jq
    bind.dnsutils
    ethtool
    tcpdump

    # Terminal Utilities
    tmux
    vim
    tree
    fastfetch
    unzip
  ];

  # --- HALOGEN FLASH SERVER ---
  virtualisation.podman = {
    enable = true;
    dockerCompat = true;
  };

  systemd.services.strix-halo-qwen-27b = {
    description = "Gufo Inference Engine for Qwen 27B";
    wantedBy = [ "multi-user.target" ];
    after = [ "network.target" "download-strix-models.service" ];
    wants = [ "download-strix-models.service" ];
    environment = {
      HSA_OVERRIDE_GFX_VERSION = "11.5.1";
    };
    serviceConfig = {
      ExecStart = gufo.lib.x86_64-linux.mkServe {
        host = "0.0.0.0";
        port = 8737;
        modality = "llm";
        model = "/var/lib/strix-halo-models/Qwen3.8-27B-Q4_K_M.gguf";
        speculative = "dflash2";
        dflashModel = "/var/lib/strix-halo-models/Qwen3.8-27B-DFlash2-Q4_K_M.gguf";
        context = 131072;
        maxTokens = 16384;
      };
      Restart = "always";
      LimitMEMLOCK = "infinity";
    };
  };

  # ------------------------------------------------------------------
  # Additional Gufo Engine Services (Disabled by default)
  # Start manually via: systemctl start strix-halo-<model>.service
  # ------------------------------------------------------------------

  systemd.services.strix-halo-flash-next = {
    description = "Gufo Inference Engine for Qwen 3.8 Flash Next";
    after = [ "network.target" ];
    environment = {
      HSA_OVERRIDE_GFX_VERSION = "11.5.1";
    };
    serviceConfig = {
      ExecStart = gufo.lib.x86_64-linux.mkServe {
        host = "0.0.0.0";
        port = 8732;
        modality = "llm";
        model = "/var/lib/strix-halo-models/Qwen3.8-Flash-Next-Q4_K_M-00001-of-00004.gguf";
        context = 32768;
        extraArgs = [ "--mmproj" "/var/lib/strix-halo-models/mmproj-Qwen3.8-Flash-Next-f16.gguf" ];
      };
      LimitMEMLOCK = "infinity";
    };
  };

  systemd.services.strix-halo-deepseek-v4-flash = {
    description = "Gufo Inference Engine for DeepSeek V4 Flash";
    after = [ "network.target" ];
    environment = {
      HSA_OVERRIDE_GFX_VERSION = "11.5.1";
    };
    serviceConfig = {
      ExecStart = gufo.lib.x86_64-linux.mkServe {
        host = "0.0.0.0";
        port = 8738;
        modality = "llm";
        model = "/var/lib/strix-halo-models/DeepSeek-V4-Flash-0731-00001-of-00008.gguf";
        context = 65536;
      };
      LimitMEMLOCK = "infinity";
    };
  };

  systemd.services.strix-halo-qwen3-asr = {
    description = "Gufo Inference Engine for Qwen3 ASR";
    after = [ "network.target" ];
    environment = {
      HSA_OVERRIDE_GFX_VERSION = "11.5.1";
    };
    serviceConfig = {
      ExecStart = gufo.lib.x86_64-linux.mkServe {
        host = "0.0.0.0";
        port = 8739;
        modality = "asr";
        model = "/var/lib/strix-halo-models/Qwen3-ASR-1.7B";
        context = 8192;
      };
      LimitMEMLOCK = "infinity";
    };
  };

  systemd.services.strix-halo-qwen3-tts = {
    description = "Gufo Inference Engine for Qwen3 TTS";
    after = [ "network.target" ];
    environment = {
      HSA_OVERRIDE_GFX_VERSION = "11.5.1";
    };
    serviceConfig = {
      ExecStart = gufo.lib.x86_64-linux.mkServe {
        host = "0.0.0.0";
        port = 8740;
        modality = "tts";
        model = "/var/lib/strix-halo-models/Qwen3-TTS-12Hz-1.7B";
        context = 4096;
      };
      LimitMEMLOCK = "infinity";
    };
  };

  systemd.services.strix-halo-qwen-image-2 = {
    description = "Gufo Inference Engine for Qwen Image 2.1";
    after = [ "network.target" ];
    environment = {
      HSA_OVERRIDE_GFX_VERSION = "11.5.1";
    };
    serviceConfig = {
      ExecStart = gufo.lib.x86_64-linux.mkServe {
        host = "0.0.0.0";
        port = 8741;
        modality = "image";
        model = "/var/lib/strix-halo-models/Qwen-Image-2.1";
        maxRequestBytes = 33554432;
      };
      LimitMEMLOCK = "infinity";
    };
  };

  systemd.services.strix-halo-minimax-h3 = {
    description = "Gufo Inference Engine for MiniMax H3 FL2VA";
    after = [ "network.target" ];
    environment = {
      HSA_OVERRIDE_GFX_VERSION = "11.5.1";
    };
    serviceConfig = {
      ExecStart = ''
        ${gufo.packages.x86_64-linux.default}/bin/gufo serve \
          --host 0.0.0.0 \
          --port 8742 \
          h3 \
          --model /var/lib/strix-halo-models/MiniMax-H3-FL2VA \
          --preset quality
      '';
      LimitMEMLOCK = "infinity";
    };
  };

  virtualisation.oci-containers = {
    backend = "podman";
    # containers."halogen" = {
    #   image = "ghcr.io/peonist-ai/halogen-flash-server:0.13.4";
    #   ports = [ "8731:8731" ];
    #   volumes = [
    #     "/var/lib/halogen-models:/models"
    #   ];
    #   environment = {
    #     HALOGEN_DOWNLOAD = "peonist-ai/halogen-qwen3.8-flash-next";
    #     HALOGEN_MAX_TOK = "16384";
    #     HALOGEN_KV_POOL_POSITIONS = "262144";
    #     HALOGEN_KV_SLOTS = "2";
    #   };
    #   extraOptions = [
    #     "--device=/dev/kfd"
    #     "--device=/dev/dri"
    #     "--group-add=keep-groups"
    #     "--ipc=host"
    #     "--ulimit=memlock=-1:-1"
    #   ];
    # };

    # containers."whisper" = {
    #   image = "docker.io/kyuz0/amd-strix-halo-toolboxes:vulkan-radv@sha256:147aae684ca987745aa4ec21ae2143dddf9bcc221f041178d91679b3ea0021b8";
    #   ports = [ "8081:8080" ];
    #   volumes = [
    #     "/var/lib/whisper-cache:/cache"
    #   ];
    #   environment = {
    #     WHISPER_VERSION = "v1.8.4";
    #     WHISPER_MODEL_FILE = "ggml-large-v3-turbo-q8_0.bin";
    #     LD_LIBRARY_PATH = "/cache/bin/v1.8.4";
    #   };
    #   # We combine the Jory initContainer download logic and the main execution into a single shell entrypoint
    #   entrypoint = "bash";
    #   cmd = [
    #     "-c"
    #     ''
    #       set -euo pipefail
    #       cd /cache
    #       if [ ! -x "bin/''${WHISPER_VERSION}/whisper-server" ]; then
    #         curl -fsSL -o w.tgz "https://github.com/lemonade-sdk/whisper.cpp-rocm/releases/download/''${WHISPER_VERSION}/whisper-''${WHISPER_VERSION}-linux-vulkan-x86_64.tar.gz"
    #         python3 -c "import tarfile;tarfile.open('w.tgz').extractall('x')"
    #         mkdir -p "bin/''${WHISPER_VERSION}"
    #         mv x/whisper-*-linux-vulkan-x86_64/* "bin/''${WHISPER_VERSION}/"
    #         rm -rf x w.tgz
    #       fi
    #       if [ ! -s "''${WHISPER_MODEL_FILE}" ]; then
    #         curl -fsSL -o "''${WHISPER_MODEL_FILE}" "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/''${WHISPER_MODEL_FILE}"
    #       fi
    #       exec /cache/bin/''${WHISPER_VERSION}/whisper-server --model "/cache/''${WHISPER_MODEL_FILE}" --host 0.0.0.0 --port 8080 --threads 4
    #     ''
    #   ];
    #   extraOptions = [
    #     "--device=/dev/kfd"
    #     "--device=/dev/dri"
    #     "--group-add=keep-groups"
    #     "--security-opt=seccomp=unconfined"
    #   ];
    # };
# 
    # containers."lemonade-tts" = {
    #   image = "ghcr.io/lemonade-sdk/lemonade-server:latest@sha256:583130946a9f57dada3e42ac047c2b842d56e041bbb5e6d38422e38746ce49eb";
    #   ports = [ "13305:13305" ];
    #   volumes = [
    #     "/var/lib/lemonade-tts-config:/opt/lemonade/.config/lemonade"
    #     "/var/lib/lemonade-tts-cache:/opt/lemonade/.cache"
    #     "/var/lib/lemonade-tts-models:/opt/lemonade/llama"
    #   ];
    #   # Combine Jory's init container config writing and the main execution
    #   entrypoint = "sh";
    #   cmd = [
    #     "-c"
    #     ''
    #       set -eu
    #       mkdir -p /opt/lemonade/.config/lemonade
    #       cat > /opt/lemonade/.config/lemonade/config.json <<'JSON'
    #       {
    #         "openmoss": {
    #           "backend": "vulkan"
    #         }
    #       }
    #       JSON
    #       exec ./lemond --host 0.0.0.0 --port 13305
    #     ''
    #   ];
    #   extraOptions = [
    #     "--device=/dev/kfd"
    #     "--device=/dev/dri"
    #     "--group-add=keep-groups"
    #   ];
    # };

    # containers."nemotron-3.5" = {
    #   image = "docker.io/kyuz0/amd-strix-halo-toolboxes:rocm-6.4.4@sha256:1c655ca0443655f2e7603d054770b07cd8c79267145728b3261295f005053947";
    #   ports = [ "8733:8080" ];
    #   volumes = [
    #     "/var/lib/strix-halo-models:/models"
    #   ];
    #   cmd = [
    #     "llama-server"
    #     "--host" "0.0.0.0"
    #     "--port" "8080"
    #     "--model" "/models/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_XL.gguf"
    #     "--alias" "nemotron-3.5-lightning-30b-a3b"
    #     "--temp" "1.0"
    #     "--top-p" "0.95"
    #     "--image-min-tokens" "1024"
    #     "--cont-batching"
    #     "--cache-prompt"
    #     "--cache-ram" "4096"
    #     "--kv-unified"
    #     "--checkpoint-min-step" "32768"
    #     "--threads" "16"
    #     "--threads-batch" "21"
    #     "--load-mode" "none"
    #   ];
    #   extraOptions = [
    #     "--device=/dev/kfd"
    #     "--device=/dev/dri"
    #     "--group-add=keep-groups"
    #   ];
    # };
    # 
    # containers."gemma-4" = {
    #   image = "docker.io/kyuz0/amd-strix-halo-toolboxes:rocm-6.4.4@sha256:1c655ca0443655f2e7603d054770b07cd8c79267145728b3261295f005053947";
    #   ports = [ "8734:8080" ];
    #   volumes = [
    #     "/var/lib/strix-halo-models:/models"
    #   ];
    #   cmd = [
    #     "llama-server"
    #     "--host" "0.0.0.0"
    #     "--port" "8080"
    #     "--model" "/models/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf"
    #     "--alias" "gemma-4-e4b"
    #     "--cont-batching"
    #     "--kv-unified"
    #     "--temp" "1.0"
    #     "--top-p" "0.95"
    #     "--top-k" "64"
    #     "--min-p" "0"
    #     "--threads" "16"
    #     "--threads-batch" "21"
    #     "--load-mode" "none"
    #   ];
    #   extraOptions = [
    #     "--device=/dev/kfd"
    #     "--device=/dev/dri"
    #     "--group-add=keep-groups"
    #   ];
    # };

    # containers."memini-embed" = {
    #   image = "docker.io/kyuz0/amd-strix-halo-toolboxes:rocm-6.4.4@sha256:1c655ca0443655f2e7603d054770b07cd8c79267145728b3261295f005053947";
    #   ports = [ "8735:8080" ];
    #   volumes = [
    #     "/var/lib/strix-halo-models:/models"
    #   ];
    #   cmd = [
    #     "llama-server"
    #     "--host" "0.0.0.0"
    #     "--port" "8080"
    #     "--model" "/models/Qwen3-Embedding-0.6B-Q8_0.gguf"
    #     "--alias" "memini-embed"
    #     "--embedding"
    #     "--cont-batching"
    #     "--kv-unified"
    #     "--threads" "6"
    #     "--threads-batch" "12"
    #     "--load-mode" "mmap"
    #   ];
    #   extraOptions = [
    #     "--device=/dev/kfd"
    #     "--device=/dev/dri"
    #     "--group-add=keep-groups"
    #   ];
    # };
    # 
    # containers."memini-rerank" = {
    #   image = "docker.io/kyuz0/amd-strix-halo-toolboxes:rocm-6.4.4@sha256:1c655ca0443655f2e7603d054770b07cd8c79267145728b3261295f005053947";
    #   ports = [ "8736:8080" ];
    #   volumes = [
    #     "/var/lib/strix-halo-models:/models"
    #   ];
    #   cmd = [
    #     "llama-server"
    #     "--host" "0.0.0.0"
    #     "--port" "8080"
    #     "--model" "/models/bge-reranker-v2-m3-Q8_0.gguf"
    #     "--alias" "memini-rerank"
    #     "--reranking"
    #     "--cont-batching"
    #     "--kv-unified"
    #     "--threads" "6"
    #     "--threads-batch" "12"
    #     "--load-mode" "mmap"
    #   ];
    #   extraOptions = [
    #     "--device=/dev/kfd"
    #     "--device=/dev/dri"
    #     "--group-add=keep-groups"
    #   ];
    # };
    
    containers."comfyui" = {
      image = "docker.io/yanwk/comfyui-boot:rocm7@sha256:c16f96a94c4760037d2d854acbe93ce594d4314b7bcb665da9f3cae225d7339c";
      ports = [ "8188:8188" ];
      volumes = [
        "/var/lib/comfyui-data:/root/ComfyUI"
      ];
      environment = {
        HSA_OVERRIDE_GFX_VERSION = "11.5.1";
        HSA_ENABLE_SDMA = "0";
        HIP_VISIBLE_DEVICES = "0";
        ROCR_VISIBLE_DEVICES = "0";
        PYTORCH_HIP_ALLOC_CONF = "max_split_size_mb:256,garbage_collection_threshold:0.6";
        CLI_ARGS = "--listen 0.0.0.0 --port 8188 --use-pytorch-cross-attention --disable-mmap --reserve-vram 114 --highvram";
      };
      extraOptions = [
        "--device=/dev/kfd"
        "--device=/dev/dri"
        "--group-add=keep-groups"
        "--security-opt=seccomp=unconfined"
        "--ipc=host"
      ];
    };

    containers."drm-exporter" = {
      image = "ghcr.io/home-operations/drm-exporter:latest";
      ports = [ "9081:8081" ];
      volumes = [
        "/sys:/sys:ro"
      ];
      extraOptions = [
        "--device=/dev/dri"
        "--cap-add=PERFMON"
        "--cap-add=SYS_RAWIO"
        "--group-add=keep-groups"
      ];
    };
  };

  # systemd.services."podman-nemotron-3.5".after = [ "download-strix-models.service" ];
  # systemd.services."podman-nemotron-3.5".wants = [ "download-strix-models.service" ];
  # systemd.services."podman-gemma-4".after = [ "download-strix-models.service" ];
  # systemd.services."podman-gemma-4".wants = [ "download-strix-models.service" ];
  # systemd.services."podman-memini-embed".after = [ "download-strix-models.service" ];
  # systemd.services."podman-memini-embed".wants = [ "download-strix-models.service" ];
  # systemd.services."podman-memini-rerank".after = [ "download-strix-models.service" ];
  # systemd.services."podman-memini-rerank".wants = [ "download-strix-models.service" ];


  # Automated model downloader
  systemd.services.download-strix-models = {
    description = "Download LLM Models for Strix Halo";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      User = "root";
    };
    script = ''
      set -e
      mkdir -p /var/lib/strix-halo-models
      cd /var/lib/strix-halo-models

      # Download Gemma 4
      if [ ! -s "gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf" ]; then
        ${pkgs.curl}/bin/curl --retry 5 -C - -L -o "gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf.tmp" "https://huggingface.co/unsloth/gemma-4-E4B-it-qat-GGUF/resolve/main/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf"
        mv "gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf.tmp" "gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf"
      fi

      # Download Nemotron 3.5 Lightning
      if [ ! -s "NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_XL.gguf" ]; then
        ${pkgs.curl}/bin/curl --retry 5 -C - -L -o "NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_XL.gguf.tmp" "https://huggingface.co/unsloth/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF/resolve/main/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_XL.gguf"
        mv "NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_XL.gguf.tmp" "NVIDIA-Nemotron-3.5-Lightning-30B-A3B-UD-Q4_K_XL.gguf"
      fi

      # Download Qwen3.8 Flash Next Q4_K_M
      if [ ! -s "Qwen3.8-Flash-Next-Q4_K_M-00001-of-00004.gguf" ]; then
        ${pkgs.curl}/bin/curl --retry 5 -C - -L -o "Qwen3.8-Flash-Next-Q4_K_M-00001-of-00004.gguf.tmp" "https://huggingface.co/bartowski/Qwen3.8-Flash-Next-GGUF/resolve/main/Qwen3.8-Flash-Next-Q4_K_M/Qwen3.8-Flash-Next-Q4_K_M-00001-of-00004.gguf"
        mv "Qwen3.8-Flash-Next-Q4_K_M-00001-of-00004.gguf.tmp" "Qwen3.8-Flash-Next-Q4_K_M-00001-of-00004.gguf"
      fi
      if [ ! -s "Qwen3.8-Flash-Next-Q4_K_M-00002-of-00004.gguf" ]; then
        ${pkgs.curl}/bin/curl --retry 5 -C - -L -o "Qwen3.8-Flash-Next-Q4_K_M-00002-of-00004.gguf.tmp" "https://huggingface.co/bartowski/Qwen3.8-Flash-Next-GGUF/resolve/main/Qwen3.8-Flash-Next-Q4_K_M/Qwen3.8-Flash-Next-Q4_K_M-00002-of-00004.gguf"
        mv "Qwen3.8-Flash-Next-Q4_K_M-00002-of-00004.gguf.tmp" "Qwen3.8-Flash-Next-Q4_K_M-00002-of-00004.gguf"
      fi
      if [ ! -s "Qwen3.8-Flash-Next-Q4_K_M-00003-of-00004.gguf" ]; then
        ${pkgs.curl}/bin/curl --retry 5 -C - -L -o "Qwen3.8-Flash-Next-Q4_K_M-00003-of-00004.gguf.tmp" "https://huggingface.co/bartowski/Qwen3.8-Flash-Next-GGUF/resolve/main/Qwen3.8-Flash-Next-Q4_K_M/Qwen3.8-Flash-Next-Q4_K_M-00003-of-00004.gguf"
        mv "Qwen3.8-Flash-Next-Q4_K_M-00003-of-00004.gguf.tmp" "Qwen3.8-Flash-Next-Q4_K_M-00003-of-00004.gguf"
      fi
      if [ ! -s "Qwen3.8-Flash-Next-Q4_K_M-00004-of-00004.gguf" ]; then
        ${pkgs.curl}/bin/curl --retry 5 -C - -L -o "Qwen3.8-Flash-Next-Q4_K_M-00004-of-00004.gguf.tmp" "https://huggingface.co/bartowski/Qwen3.8-Flash-Next-GGUF/resolve/main/Qwen3.8-Flash-Next-Q4_K_M/Qwen3.8-Flash-Next-Q4_K_M-00004-of-00004.gguf"
        mv "Qwen3.8-Flash-Next-Q4_K_M-00004-of-00004.gguf.tmp" "Qwen3.8-Flash-Next-Q4_K_M-00004-of-00004.gguf"
      fi
      if [ ! -s "mmproj-Qwen3.8-Flash-Next-f16.gguf" ]; then
        ${pkgs.curl}/bin/curl --retry 5 -C - -L -o "mmproj-Qwen3.8-Flash-Next-f16.gguf.tmp" "https://huggingface.co/bartowski/Qwen3.8-Flash-Next-GGUF/resolve/main/mmproj-Qwen3.8-Flash-Next-f16.gguf"
        mv "mmproj-Qwen3.8-Flash-Next-f16.gguf.tmp" "mmproj-Qwen3.8-Flash-Next-f16.gguf"
      fi

      # Download Qwen3.8 27B
      if [ ! -s "Qwen3.8-27B-Q4_K_M.gguf" ]; then
        ${pkgs.curl}/bin/curl --retry 5 -C - -L -o "Qwen3.8-27B-Q4_K_M.gguf.tmp" "https://huggingface.co/bartowski/Qwen3.8-27B-GGUF/resolve/main/Qwen3.8-27B-Q4_K_M.gguf"
        mv "Qwen3.8-27B-Q4_K_M.gguf.tmp" "Qwen3.8-27B-Q4_K_M.gguf"
      fi

      # Download Memini Embed
      if [ ! -s "Qwen3-Embedding-0.6B-Q8_0.gguf" ]; then
        ${pkgs.curl}/bin/curl --retry 5 -C - -L -o "Qwen3-Embedding-0.6B-Q8_0.gguf.tmp" "https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/resolve/main/Qwen3-Embedding-0.6B-Q8_0.gguf"
        mv "Qwen3-Embedding-0.6B-Q8_0.gguf.tmp" "Qwen3-Embedding-0.6B-Q8_0.gguf"
      fi

      # Download Memini Rerank
      if [ ! -s "bge-reranker-v2-m3-Q8_0.gguf" ]; then
        ${pkgs.curl}/bin/curl -L -o "bge-reranker-v2-m3-Q8_0.gguf.tmp" "https://huggingface.co/gpustack/bge-reranker-v2-m3-GGUF/resolve/main/bge-reranker-v2-m3-Q8_0.gguf"
        mv "bge-reranker-v2-m3-Q8_0.gguf.tmp" "bge-reranker-v2-m3-Q8_0.gguf"
      fi
    '';
  };

  # Podman requires bind mount source directories to exist beforehand
  systemd.tmpfiles.rules = [
    "d /var/lib/halogen-models 0755 root root -"
    "d /var/lib/strix-halo-models 0755 root root -"
    "d /var/lib/whisper-cache 0755 root root -"
    "d /var/lib/lemonade-tts-config 0777 root root -"
    "d /var/lib/lemonade-tts-cache 0777 root root -"
    "d /var/lib/lemonade-tts-models 0777 root root -"
    "d /var/lib/comfyui-data 0755 root root -"
  ];

  # --- TELEMETRY AGENT (single agent: logs, metrics, profiles, traces) ---
  # Pushes all four signals to the in-cluster alloy-receiver gateway via envoy-internal:
  #   logs      -> https://logs-ingest.cloudjur.com/loki/api/v1/push
  #   metrics   -> https://metrics-ingest.cloudjur.com/api/v1/write
  #   profiles  -> https://profiles-ingest.cloudjur.com/ingest
  #   traces    -> https://traces-ingest.cloudjur.com  (OTLP/HTTP, via beyla.ebpf)
  #
  # NOTE: pyroscope.ebpf and beyla.ebpf require root + BTF (present on this
  # kernel), so the upstream DynamicUser default is overridden below.
  environment.etc."alloy/config.alloy".text = ''
    // ------------------------------------------------------------------
    // LOGS: journald (halogen container + host) -> Loki
    // ------------------------------------------------------------------
    loki.relabel "journal" {
      forward_to = []

      rule {
        source_labels = ["__journal__systemd_unit"]
        target_label  = "unit"
      }
      rule {
        source_labels = ["__journal_priority_keyword"]
        target_label  = "level"
      }
    }

    loki.source.journal "host" {
      forward_to    = [loki.write.ingest.receiver]
      relabel_rules = loki.relabel.journal.rules
      labels        = { node = "strix-halo", source = "journald" }
    }

    loki.write "ingest" {
      endpoint {
        url = "https://logs-ingest.cloudjur.com/loki/api/v1/push"
        max_backoff_period = "5m"
      }
    }

    // ------------------------------------------------------------------
    // METRICS: scrape local node-exporter + halogen -> Prometheus remote-write
    // Labels replicate the previous pull-based ScrapeConfigs exactly so the
    // dashboards keep working after the pull targets were removed.
    // ------------------------------------------------------------------
    prometheus.scrape "node_exporter" {
      targets = [
        { __address__ = "127.0.0.1:9100", instance = "192.168.1.149:9100" },
      ]
      forward_to = [prometheus.relabel.node_exporter.receiver]
    }

    prometheus.relabel "node_exporter" {
      rule {
        target_label = "job"
        replacement  = "node-exporter"
      }
      forward_to = [prometheus.remote_write.ingest.receiver]
    }

    prometheus.scrape "gufo" {
      targets = [
        { __address__ = "127.0.0.1:8732", instance = "192.168.1.149:8732" },
        { __address__ = "127.0.0.1:8737", instance = "192.168.1.149:8737" },
        { __address__ = "127.0.0.1:8738", instance = "192.168.1.149:8738" },
        { __address__ = "127.0.0.1:8739", instance = "192.168.1.149:8739" },
        { __address__ = "127.0.0.1:8740", instance = "192.168.1.149:8740" },
        { __address__ = "127.0.0.1:8741", instance = "192.168.1.149:8741" },
        { __address__ = "127.0.0.1:8742", instance = "192.168.1.149:8742" },
      ]
      forward_to = [prometheus.relabel.gufo.receiver]
    }

    prometheus.relabel "gufo" {
      rule {
        target_label = "job"
        replacement  = "gufo"
      }
      rule {
        target_label = "namespace"
        replacement  = "llm"
      }
      rule {
        target_label = "node"
        replacement  = "strix-halo"
      }
      rule {
        target_label = "service"
        replacement  = "gufo"
      }
      forward_to = [prometheus.remote_write.ingest.receiver]
    }

    prometheus.remote_write "ingest" {
      endpoint {
        url = "https://metrics-ingest.cloudjur.com/api/v1/write"
      }
    }

    // ------------------------------------------------------------------
    // PROFILES: eBPF CPU profiling of the gufo process -> Pyroscope
    // ------------------------------------------------------------------
    pyroscope.ebpf "gufo" {
      targets = [
        { __address__ = "gufo" },
      ]
      forward_to = [pyroscope.write.ingest.receiver]
    }

    pyroscope.write "ingest" {
      endpoint {
        url = "https://profiles-ingest.cloudjur.com/ingest"
      }
    }

    // ------------------------------------------------------------------
    // TRACES: eBPF auto-instrumentation of gufo HTTP -> OTLP
    // Runs inside Alloy as a child process (same root/eBPF perms as profiling).
    // Discovery by open_ports works across the container netns because Alloy
    // runs on the host as root and sees every socket via eBPF.
    // ------------------------------------------------------------------
    beyla.ebpf "gufo" {
      discovery {
        instrument {
          open_ports = "8732,8737,8738,8739,8740,8741,8742"
          name       = "gufo"
        }
      }
      traces {
        instrumentations = ["http"]
      }
      output {
        traces = [otelcol.processor.batch.traces.input]
      }
    }

    otelcol.processor.batch "traces" {
      output {
        traces = [otelcol.exporter.otlphttp.traces.input]
      }
    }

    otelcol.exporter.otlphttp "traces" {
      client {
        endpoint = "https://traces-ingest.cloudjur.com"
      }
    }
  '';

  services.alloy = {
    enable = true;
    extraFlags = [ "--server.http.listen-addr=127.0.0.1:12345" ];
  };

  # pyroscope.ebpf needs root (eBPF + perf events); drop the DynamicUser default.
  systemd.services.alloy = {
    serviceConfig = {
      DynamicUser = lib.mkForce false;
      User = lib.mkForce "root";
      SupplementaryGroups = [ "systemd-journal" ];
    };
    # wait for network so the ingest endpoints resolve at startup
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
  };

  # NOTE: Tracing is handled by the beyla.ebpf component inside Alloy (see the
  # config.alloy block above). The previous standalone Beyla container was
  # removed because ghcr.io/grafana/beyla:latest is no longer publicly
  # pullable — Beyla's images migrated to Google Artifact Registry and the
  # project was donated to OpenTelemetry (now OBI). Running beyla.ebpf inside
  # Alloy keeps a single telemetry agent on this host.
}
