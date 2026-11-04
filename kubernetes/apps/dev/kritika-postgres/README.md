# Kritika Postgres (spike)

**Description:** CloudNativePG cluster (PostgreSQL 18 + VectorChord) proving spec
`home-ops-agent/specs/003-kritika-review-service` **SC-001** on this cluster before the Kritika
app itself is deployed. Nothing consumes this database yet.
**Category:** database

## Resources
- **Manifests:** `kubernetes/apps/dev/kritika-postgres`
- **Upstream pattern:** <https://kritika.home-operations.com/database/> (CNPG 1.30, verified 2026-11-04)
- **Desk-spike evidence:** `ai-sandbox/home-ops-agent/specs/003-kritika-review-service/results/001-vectorchord-compat.md`

## Notes (the five pillars)

- **DR & bootstrapping:** Spike-grade: `bootstrap.initdb`, no barman/backup wiring yet — that is
  FR-009 of spec `003` and lands with the app PR (barman → garage, like `database/cloudnative-pg`).
  Accepted data-loss stance: the index is regenerable from the repos; reviews live on GitHub.
- **Network:** cluster-internal only. Consumers connect to the **direct** `-rw` service;
  transaction-mode pooling (`Pooler`) is FORBIDDEN for this database (breaks advisory locks/LISTEN
  per upstream). No ingress, no external exposure.
- **Maintenance:** image + `vchord-scratch` are digest-pinned; bumps = one PR changing BOTH
  `cluster.yaml` tags and `database.yaml`'s `vchord` version together (CNPG updates the extension
  when the declared version changes). `primaryUpdateStrategy` intentionally left default (the
  existing shared cluster's unsupervised setting is its own history).
- **Storage:** `miroir-local`, 10 Gi, single instance — single node, so `instances: 1` and no
  anti-affinity (deliberate deviation from upstream's 2-instance example, which cannot schedule
  here). Node-local storage class is correct: Postgres replicates logically; the storage layer
  need not (upstream database.md).
- **Security & IAM:** `enableSuperuserAccess: false`. Two roles per upstream: owner `kritika`
  (initdb, runs migrations, NOT superuser) and app `kritika_app` via `DatabaseRole` (no table
  ownership, no BYPASSRLS — Kritika refuses anything else). Passwords are ESO `Password`-generated
  at reconcile (`refreshInterval: Never` → generatorState is the persistence), URI-safe charset,
  never in Git. TODO before the real app install: move both into Bitwarden via
  `bitwarden-login` like the shared cluster, so they survive a dev-namespace wipe review.

## Verifying the spike (SC-001 closure)

After Flux applies:

```sh
kubectl -n dev get cluster kritika-postgres          # Cluster in healthy state
kubectl -n dev get database kritika                  # reconciled, extensions present
# both extensions must exist or Kritika's own startup check refuses (ErrNoVectorExtension):
kubectl -n dev exec kritika-postgres-1 -- psql -U kritika -d kritika -c \
  "SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector','vchord') ORDER BY 1;"
# index method proof (upstream integration test's assertion):
kubectl -n dev exec kritika-postgres-1 -- psql -U kritika -d kritika -c \
  "CREATE TABLE _spike(id int, e halfvec(4));
   INSERT INTO _spike VALUES (1,'[1,0,0,0]');
   CREATE INDEX ON _spike USING vchordrq (e halfvec_cosine_ops);
   SELECT indexdef FROM pg_indexes WHERE tablename='_spike';
   DROP TABLE _spike;"
```

Expected: `vector 0.8.x` + `vchord 1.1.1`, and an index definition starting
`CREATE ... USING vchordrq`. Paste output back into the spec's `results/` as `002-*`.
