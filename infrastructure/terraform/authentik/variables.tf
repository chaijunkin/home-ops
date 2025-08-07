
variable "CLUSTER_DOMAIN" {
  type        = string
  description = "Domain for Authentik"
  sensitive   = true
}

# variable "gitops_id" {
#   type        = string
#   description = "Weave-Gitops Client ID"
#   sensitive   = true
# }

# variable "gitops_secret" {
#   type        = string
#   description = "Weave-Gitops Client Secret"
#   sensitive   = true
# }

variable "grafana_id" {
  type        = string
  description = "Grafana Client ID"
  sensitive   = true
}

variable "grafana_secret" {
  type        = string
  description = "Grafana Client Secret"
  sensitive   = true
}

variable "headlamp_id" {
  type        = string
  description = "Headlamp Client ID"
  sensitive   = true
  default = null
}

variable "headlamp_secret" {
  type        = string
  description = "Headlamp Client Secret"
  sensitive   = true
  default = null
}

# variable "paperless_id" {
#   type        = string
#   description = "Paperless Client ID"
#   sensitive   = true
# }

# variable "paperless_secret" {
#   type        = string
#   description = "Paperless Client Secret"
#   sensitive   = true
# }

variable "oauth_client_id" {
  type        = string
  description = "OAuth Client ID (google)"
  sensitive   = true
}

variable "oauth_client_secret" {
  type        = string
  description = "OAuth Client Secret (google)"
  sensitive   = true
}

variable "authentik_token" {
  type        = string
  description = "Authentik Token"
  sensitive   = true
}
