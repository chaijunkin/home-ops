
variable "public_domain" {
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

variable "open_webui_id" {
  type        = string
  description = "Open Web UI Client ID"
  sensitive   = true
}

variable "open_webui_secret" {
  type        = string
  description = "Open Web UI Client Secret"
  sensitive   = true
}


variable "headlamp_id" {
  type        = string
  description = "Headlamp Client ID"
  sensitive   = true
  default     = null
}

variable "headlamp_secret" {
  type        = string
  description = "Headlamp Client Secret"
  sensitive   = true
  default     = null
}

variable "jellyfin_id" {
  type        = string
  description = "Jellyfin Client ID"
  sensitive   = true
  default     = null
}

variable "jellyfin_secret" {
  type        = string
  description = "Jellyfin Client Secret"
  sensitive   = true
  default     = null
}


variable "ocis_id" {
  type        = string
  description = "OCIS Client ID"
  sensitive   = true
  default     = null
}

variable "ocis_secret" {
  type        = string
  description = "OCIS Client Secret"
  sensitive   = true
  default     = null
}

variable "calibre_web_automated_id" {
  type        = string
  description = "calibre_web_automated client id"
  sensitive   = true
  default     = null
}

variable "calibre_web_automated_secret" {
  type        = string
  description = "calibre_web_automated client secret"
  sensitive   = true
  default     = null
}

variable "karakeep_id" {
  type        = string
  description = "karakeep client id"
  sensitive   = true
  default     = null
}

variable "karakeep_secret" {
  type        = string
  description = "karakeep client secret"
  sensitive   = true
  default     = null
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
