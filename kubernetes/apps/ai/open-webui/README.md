# Open-Webui

**Description:** To be filled.
**Category:** ai

---

## Resources
- **Project Repository:** [Open-Webui Source Code](https://github.com/search?q=open-webui)
- **Helm/Manifest Source:** `Unknown`

---

## Related Links
- [Documentation]() <!-- Add link to upstream docs -->
- [Application PRR Document](https://wiki.cloudjur.com/pages/tech/cloudjur/application/open-webui)

## Notes
- MCP is managed via toolhive
- LLM lists (Date: 2026-06-28)
  - Google
    - url: https://generativelanguage.googleapis.com/v1beta/openai
    - default model: flash
  - OpenRouter
    - url: https://openrouter.ai/api/v1
    - default model: nvidia
    - pros:
      - general use case
    - limitation:
      - daily refresh
  - Cerebras
    - url: https://api.cerebras.ai/v1
    - default model: gpt-oss-120b/zai-glm-4.7
    - pros:
      - ok-ish models
    - limitation:
      - not sure context
  - Huggingface
    - url: https://router.huggingface.co/v1
    - default model:
    - pros:
      - a lot models
    - limitation:
      - less limit, refresh monthly
  - Groq
    - url: https://api.groq.com/openai/v1
    - default model: GPT OSS/LLAMA
    - pros:
      - good for ai metaprompt (prompt engine based on requirement)
    - limitation:
      - low context limit
  - Mistral
    - url: https://api.mistral.ai/v1
    - default model: code-XX
    - pros:
      - generous use case for development
    - limitation:
      - quality
  - Vercel
    - url: https://ai-gateway.vercel.sh/v1
    - default model:
      -
