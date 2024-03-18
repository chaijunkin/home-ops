locals {
  buckets = [
    "loki",
    "thanos",
    "volsync",
    "postgresql",
    "tagspaces"
  ]
}

module "minio_bucket" {
  for_each    = toset(local.buckets)
  source      = "./modules/minio_bucket"
  bucket_name = each.key
  user_name   = random_password.user_name[each.key].result
  user_secret = random_password.user_secret[each.key].result
  providers = {
    minio = minio.nas
  }
}

output "minio_bucket_outputs" {
  value     = module.minio_bucket
  sensitive = true
}

resource "random_password" "user_name" {
  for_each = toset(local.buckets)
  length   = 32
  special  = false
}

resource "random_password" "user_secret" {
  for_each = toset(local.buckets)
  length   = 32
}
