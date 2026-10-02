# Toolhive

**Description:** Operator deploying and securing MCP servers.
**Category:** ai

---

## Resources
- **Project Repository:** [Toolhive Source Code](https://github.com/stacklok/toolhive)
- **Helm/Manifest Source:** `Unknown`

---

## Related Links
- [Documentation](https://docs.stacklok.com/toolhive)
- [Application PRR Document](https://wiki.cloudjur.com/pages/tech/cloudjur/application/toolhive)

## Internal MCP optimizer

The internal `mcp-direct.cloudjur.com` VirtualMCPServer uses ToolHive's
optimizer so clients receive `find_tool` and `call_tool` instead of the full
backend tool catalog. Its optimizer calls the `embed` model
through LiteLLM's in-cluster OpenAI-compatible API. LiteLLM routes that alias
to the existing Qwen3-Embedding-0.6B service on Strix Halo; no additional
EmbeddingServer or llmkube workload is required. ToolHive uses a dedicated
LiteLLM virtual key scoped to the `embed` model.

The authenticated `mcp.cloudjur.com` gateway remains unoptimized. The
optimizer currently negotiates MCP protocol version `2025-11-25`; clients
advertising the newer `2026-07-28` protocol may be downgraded while using the
optimizer. ToolHive returns up to eight matching tools by default.

## Notes
- *Add operational notes, gotchas, or specific configurations here.*
