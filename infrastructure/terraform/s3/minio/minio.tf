locals {
  minio_buckets = [
    "loki",
    "thanos",
    "volsync",
    "postgresql",
    "tagspaces"
  ]
}

module "minio_bucket" {
  for_each    = toset(local.minio_buckets)
  source      = "./modules/minio_bucket"
  bucket_name = each.key
  is_public   = false
  # owner_access_key = var.owner_access_key
  # owner_secret_key = var.owner_secret_key
  providers = {
    minio = minio.nas
  }
}
output "minio_bucket_outputs" {
  value     = module.minio_bucket
  sensitive = true
}
