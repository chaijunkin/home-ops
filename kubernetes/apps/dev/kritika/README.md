# Kritika Postgres (spike)

**Description:** CloudNativePG cluster (PostgreSQL 18 + VectorChord) proving spec
`home-ops-agent/specs/003-kritika-review-service` **SC-001** on this cluster before the Kritika
app itself is deployed. Nothing consumes this database yet.
**Category:** database

## Resources
- **Manifests:** `kubernetes/apps/dev/kritika` — `database/` (cluster, extensions, roles,
  credentials) and `backup/` (daily dump job). The Kritika app lands as `app/` beside them in a
  follow-up PR; folder layout follows bjw-s and onedr0p/home-ops (`kritika-database` ← `kritika`).
- **Upstream pattern:** <https://kritika.home-operations.com/database/> (CNPG 1.30, verified 2026-11-04)
- **Desk-spike evidence:** `ai-sandbox/home-ops-agent/specs/003-kritika-review-service/results/001-vectorchord-compat.md`

## Notes (the five pillars)

- **DR & bootstrapping:** Manual pipeline (user decision 2026-11-04, same posture as the shared
  `database/cloudnative-pg`): daily `pg_dump` CronJob (`prodrigestivill/postgres-backup-local`,
  same digest as the shared job) → NFS `smb.cloudjur.com:/tank/Backup/Database`; the tool's
  host-named subdirectory (`kritika-postgres-rw`) keeps these dumps separate from the shared
  cluster's. Credentials map from the owner Secret via `valueFrom` — nothing new to store.
  Barman/CNPG-native backup deliberately NOT used (mirrors the folder convention the operator
  set for Postgres). Accepted stance: the vector index is regenerable from the repos; reviews
  live on GitHub.
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
- **Security & IAM:** `enableSuperuserAccess: false`, `enablePDB: false` (single instance — a
  primary PDB would block node drains). Two roles per upstream: owner `kritika`
  (initdb, runs migrations, NOT superuser) and app `kritika_app` via `DatabaseRole` (no table
  ownership, no BYPASSRLS — Kritika's startup assertion refuses anything else). Both credentials
  come from **one Bitwarden login item** `6472239d-…` (operator decision 2026-11-04: no runtime
  generators — the owner password is baked into the DB at `initdb`, so the credential must outlive
  the cluster state storing it): owner = the item's login username/password via `bitwarden-login`,
  app = custom fields `app_username`/`app_password` via `bitwarden-fields` (85 files fleet-wide use
  this store). Two distinct roles are NOT optional — one role doing both jobs makes Kritika refuse
  to start, because a table-owning app role silently disables every row-level-security policy.
  UUIDs are the only Git-visible handle; passwords never are. Keep both passwords alphanumeric so
  the templated connection URI needs no escaping.

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
