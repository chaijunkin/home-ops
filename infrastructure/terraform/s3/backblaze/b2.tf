
resource "random_pet" "server" {}

resource "b2_bucket" "cnpg-backup" {

  bucket_name = "cnpg-backup-${random_pet.server.id}"
  bucket_type = "allPrivate"

}

# resource "b2_bucket" "tf-s3-state" {
#   bucket_name = "tf-s3-state-${random_pet.server.id}"
#   bucket_type = "allPrivate"
# }

# resource "b2_application_key" "tf-s3-state" {
#   key_name = "tf-s3-state"
#   capabilities = [
#     "deleteFiles",
#     "listAllBucketNames",
#     "listBuckets",
#     "listFiles",
#     "readBuckets",
#     "writeBuckets",
#     "readFiles",
#     "shareFiles",
#     "writeFiles"
#   ]
# }

resource "b2_bucket" "vw-backup" {

  bucket_name = "vw-backup-${random_pet.server.id}"
  bucket_type = "allPrivate"

  file_lock_configuration {
    is_file_lock_enabled = true
    # default_retention {
    #   mode = "governance"
    #   period {
    #     duration = 30
    #     unit     = "days"
    #   }
    # }
  }
}

resource "b2_application_key" "vw-restic" {
  key_name = "vw-restic"
  capabilities = [
    "deleteFiles",
    "listAllBucketNames",
    "listBuckets",
    "listFiles",
    "readBuckets",
    "readFiles",
    "shareFiles",
    "writeFiles"
  ]
}
