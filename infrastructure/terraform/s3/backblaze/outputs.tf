## EMERGENCY ACCESS
## terraform output -raw <OUTPUT>
output "b2_application_key" {
  value     = b2_application_key.vw-restic.application_key
  sensitive = true
}

output "b2_application_key_id" {
  value     = b2_application_key.vw-restic.application_key_id
  sensitive = true
}

# output "tf_s3_state_b2_application_key" {
#   value     = b2_application_key.tf-s3-state.application_key
#   sensitive = true
# }

# output "tf_s3_state_b2_application_key_id" {
#   value     = b2_application_key.tf-s3-state.application_key_id
#   sensitive = true
# }
