# Sure

**Description:** Self-hosted personal finance manager.
**Category:** default

---

## Resources
- **Project Repository:** [Sure Source Code](https://github.com/we-promise/sure)
- **Helm/Manifest Source:** `Unknown`

---

## Related Links
- [Documentation]() <!-- Add link to upstream docs -->
- [Application PRR Document](https://wiki.cloudjur.com/pages/tech/cloudjur/application/sure)

## Notes
- The image is pinned to `stable@sha256:...`; Renovate digest bumps re-point the
  pin. Both `web` and `worker` run a `migration` initContainer (`rake db:prepare`)
  before their app containers start, so every image change applies pending Rails
  migrations before new code serves traffic or Sidekiq jobs. Keep that
  initContainer on any future refactor - without it the schema drifts behind the
  image and new features stay broken.
- Do not remove the explicit `command` on the web container unless intentionally
  relying on the image entrypoint's own `db:prepare`.
