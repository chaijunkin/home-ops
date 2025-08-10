# Input Variables
# https://www.terraform.io/language/values/variables

variable "cloudflare_api_token" {
  description = "Cloudflare API Token"
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare Account ID"
  sensitive   = true
}

variable "cloudflare_zone_name" {
  description = "Cloudflare Zone Name (DNS name)"
}


variable "mail_txt_value" {
  description = "Mail TXT value"
  sensitive   = true
}

variable "mail_mx1_value" {
  description = "Mail MX 1 value"
  sensitive   = true
}

variable "mail_mx2_value" {
  description = "Mail MX 2 value"
  sensitive   = true
}

variable "mail_spf_value" {
  description = "Mail SPF value"
  sensitive   = true
}

variable "dkim_value" {
  description = "DKIM value, DKIM is an email validation system that uses encryption to validate if an email has been sent from authorized servers configured by the administrator of the domain. Add a selector and enter the generated TXT Record value in your DNS provider to activate DKIM for your domain"
  sensitive   = true
}

variable "dmarc_value" {
  description = "DMARC value, DMARC is an email authentication protocol. It builds on the widely deployed SPF and DKIM protocols. Additionally, it includes a reporting function that allows senders and receivers to monitor and protect their domain from fraudulent email."
  sensitive   = true
}
