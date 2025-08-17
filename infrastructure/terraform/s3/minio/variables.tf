variable "minio_server" {
  description = "Minio server URL (S3)"
  type        = string
  sensitive   = true
}

variable "minio_user" {
  description = "Minio User"
  type        = string
  sensitive   = true
}

variable "minio_password" {
  description = "Minio user password. Required, sensitive"
  type        = string
  sensitive   = true
}

variable "owner_access_key" {
  description = "Bucket Owner access key"
  type        = string
  sensitive   = true
}

variable "owner_secret_key" {
  description = "Buket Owner secret key"
  type        = string
  sensitive   = true
}