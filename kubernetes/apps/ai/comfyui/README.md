# Comfyui

**Description:** Node-based graphical interface and backend for Stable Diffusion image generation.
**Category:** ai

---

## Resources
- **Project Repository:** [Comfyui Source Code](https://github.com/comfyanonymous/ComfyUI)
- **Helm/Manifest Source:** `Unknown`

---

## Related Links
- [Documentation](https://docs.comfy.org)
- [Application PRR Document](https://wiki.cloudjur.com/pages/tech/cloudjur/application/comfyui)

## Notes
- The ComfyUI service runs on the Strix Halo NixOS host (`192.168.1.149:8188`) and is routed internally by the Service, Endpoints, and HTTPRoute in `app/external.yaml`.
- Model files must be installed in `/var/lib/comfyui-data/models/` on Strix Halo before image-generation workflows can run.
- The `misospace/miso-gallery` companion serves generated output (`miso-gallery/`).
