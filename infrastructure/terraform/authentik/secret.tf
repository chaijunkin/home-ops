# data "bitwarden-secrets_secret" "secret" {
#   id = [for s in data.bitwarden-secrets_list_secrets.secrets.secrets : s.id if s.key == "TF_VAR_authentik_token"][0]
# }

# output "secret_value" {
#   sensitive = true
#   value = data.bitwarden-secrets_secret.secret.value
# }

# data "bitwarden-secrets_list_secrets" "secrets" {}

# output "secrets" {
#   value = data.bitwarden-secrets_list_secrets.secrets
# }