# LLM Strategy & Model Routing

This document outlines the LLM deployment topology and traffic routing strategy for this infrastructure, heavily inspired by JoryIrving's split-lane architecture but adapted for local UMA memory on the AMD Strix Halo APU.

## Architecture

The cluster orchestrates traffic through **LiteLLM**, separating highly sensitive workloads (local execution) from concurrent bulk workloads (cloud/API execution) via predefined pools and model aliases.

### 1. Local execution (Strix Halo)
Our local APU is leveraged for maximum privacy, unbounded context processing, and low-latency feedback loops. Memory is UMA-shared, allowing us to load substantial models natively without VRAM limits.
- **`qwen3.8-27b`**: The primary text-only coding lane. Exceptionally fast for its size, handled via vLLM.
- **`qwen3.8-flash-next`**: The vision-capable agentic lane. Used for high-context synthesis and multimodal recon.
- **`gemma-4-12b-it-qat`**: Alternative lane for specialized context processing.

### 2. High-Availability Cloud Pools
For workloads that can leave the cluster or require massive concurrent fan-out, we utilize abstracted "pools" in LiteLLM to load-balance across API providers.
- **`frontier-pool`**: High-capability premium models (e.g., `GLM 5.3 Flash`, `MiniMax M3`, `Kimi K3`). Used for deep reasoning, architectural review, and complex multi-file implementations.
- **`reasoning-pool`**: Specialized endpoints focused entirely on chain-of-thought operations.
- **`public-pool` / `free-pool`**: Free-tier or low-cost APIs (e.g., `gemini-2.5-flash`, `groq`). Used for non-private internet recon, codebase summarization, and formatting tasks. Data sent here must not contain secrets or proprietary code.

## OpenCode Subagent Routing

The OpenCode agents use a hybrid delegation strategy to maximize speed while protecting core logic.

1. **Coordinator & Coder (`coordinator-local`, `coder-local`)**: Pinned to the Strix Halo local models. This ensures the primary thought loop and core codebase changes never leave the local network.
2. **Implementer (`implementer`)**: Delegated to the `frontier-pool`. Mechanical refactors and bulk file edits are fanned out concurrently across cloud APIs to overcome the single-node bottleneck.
3. **Reviewer & Explorer (`reviewer`, `explorer`)**: Delegated to premium cloud endpoints (e.g., MiniMax-M3, Kimi K2.7). They act as adversarial second-opinions and codebase scouts, operating in parallel to the local Coder.

### Adding New Pools
To add new models to a pool (e.g., a fallback for the `public-pool`), create a new manifest in `app/models/` (e.g., `public-pool-2.yaml`) using the same `modelName: public-pool` but a lower priority `order` value in `additional.order`. LiteLLM will automatically treat them as a load-balanced group.
