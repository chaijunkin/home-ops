# Kritika Review Service & Postgres

**Description:** Repository-aware AI PR reviewer (`home-operations/kritika`) backed by a dedicated
CloudNativePG cluster (PostgreSQL 18 + VectorChord) and in-cluster LiteLLM gateway.
**Category:** dev / review

## Resources
- **Manifests:** `kubernetes/apps/dev/kritika` — `database/` (cluster, extensions, roles, credentials),
  `backup/` (daily dump job), and `app/` (Kritika serve Deployment, HTTPRoute, ExternalSecret, NetworkPolicy).
  Folder layout follows bjw-s and onedr0p/home-ops (`kritika-database` ← `kritika` Kustomization chain).
- **Upstream pattern:** <https://kritika.home-operations.com/> (chart `0.0.117`)
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
- **Network & Routing:** 
  - Database: cluster-internal only. Direct connection to `-rw` service (no transaction pooling/Pooler).
  - Webhooks & Dashboard: exposed via Gateway API `HTTPRoute` parented to `envoy-external` (`sectionName: https`)
    at `https://kritika.cloudjur.com`. External-dns automatically registers the Cloudflare DNS record.
  - Egress: Runner forward proxy allows all external traffic but denies RFC1918 / internal networks.
    CiliumNetworkPolicy allows Kritika serve to reach in-cluster LiteLLM on `ai/litellm:4000` and external `api.github.com:443`.
- **Maintenance:** image + `vchord-scratch` are digest-pinned; bumps = one PR changing BOTH
  `cluster.yaml` tags and `database.yaml`'s `vchord` version together. Chart `0.0.117` pinned in `ocirepository.yaml`.
- **Storage:** `miroir-local`, 10 Gi, single instance (`instances: 1`, no anti-affinity). Node-local storage
  class is correct: Postgres replicates logically; storage layer need not.
- **Security & IAM:** `enableSuperuserAccess: false`, `enablePDB: false` (single instance).
  - DB roles: owner `kritika` (migrations) and app `kritika_app` (runtime queries).
  - Credentials: all sourced from Bitwarden via ExternalSecrets:
    - DB owner/app: `6472239d-…` (Kritika hub login item).
    - GitHub App: `fd77a223-…` (`cjk-bot` app ID and private key note).
    - LiteLLM Virtual Key: `bf2fcc14-…` (`LITELLM_VIRTUAL_KEY`).
  - Human Gate: `review.approve: false` — reviews only, never auto-approves or auto-merges.

## Verifying the Deployment

After Flux applies:

```sh
# 1. Verify Database
kubectl -n dev get cluster kritika-postgres
kubectl -n dev get database kritika

# 2. Verify Extensions
kubectl -n dev exec kritika-postgres-1 -- psql -U kritika -d kritika -c \
  "SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector','vchord') ORDER BY 1;"

# 3. Verify App & Routing
kubectl -n dev get helmrelease kritika
kubectl -n dev get httproute kritika
curl -fsSL https://kritika.cloudjur.com/api/v1/meta
```
