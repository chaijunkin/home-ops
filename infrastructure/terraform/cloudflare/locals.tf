
locals {
  cloudflare_zone_name  = var.cloudflare_zone_name
  cloudflare_account_id = var.cloudflare_account_id
  cloudflare_api_token  = var.cloudflare_api_token

  mail_txt_value                            = var.mail_txt_value
  mail_mx1_value                            = var.mail_mx1_value
  mail_mx2_value                            = var.mail_mx2_value
  mail_spf_value                            = var.mail_spf_value
  mail_domain_verification_key_txt_hostname = var.mail_domain_verification_key_txt_hostname
  mail_domain_verification_key_txt_value    = var.mail_domain_verification_key_txt_value
  dkim_value                                = var.dkim_value
  dmarc_value                               = var.dmarc_value

  # google auth
  google_verification_txt_value = var.google_verification_txt_value

  cloudflare_record = {
    # "mail_txt" = {
    #   name  = "@"
    #   value = local.mail_txt_value
    #   type  = "TXT"
    # }
    "ftp" = {
      name  = "ftp"
      value = local.mail_mx1_value
      type  = "CNAME"
    }
    "webmail" = {
      name  = "webmail"
      value = local.mail_mx1_value
      type  = "CNAME"
    }
    "mail" = {
      name  = "mail"
      value = local.mail_mx1_value
      type  = "CNAME"
    }
    "imap" = {
      name  = "imap"
      value = local.mail_mx1_value
      type  = "CNAME"
    }
    "pop" = {
      name  = "pop"
      value = local.mail_mx1_value
      type  = "CNAME"
    }
    "smtp" = {
      name  = "smtp"
      value = local.mail_mx1_value
      type  = "CNAME"
    }
    ## This maybe don't need
    # "mail_mx0" = {
    #   name     = "${local.cloudflare_zone_name}."
    #   value    = "mail.${local.cloudflare_zone_name}"
    #   type     = "MX"
    #   priority = 5
    # }
    "mail_mx1" = {
      name     = "@"
      value    = local.mail_mx1_value
      type     = "MX"
      priority = 10
    }
    "mail_mx2" = {
      name     = "@"
      value    = local.mail_mx2_value
      type     = "MX"
      priority = 20
    }
    "mail_spf" = {
      name  = "@"
      value = local.mail_spf_value
      type  = "TXT"
    }
    "mail_domain_verification_key" = {
      name  = local.mail_domain_verification_key_txt_hostname
      value = local.mail_domain_verification_key_txt_value
      type  = "TXT"
    }
    "google_verification" = {
      name  = local.cloudflare_zone_name
      value = local.google_verification_txt_value
      type  = "TXT"
      ttl   = 1
    }
    "mail_dkim" = {
      name  = "x._domainkey"
      value = local.dkim_value
      type  = "TXT"
      ttl   = 1
    }
    "mail_dmarc" = {
      name  = "_dmarc"
      value = local.dmarc_value
      type  = "TXT"
    }
    # "gitops-docs" = {
    #   name    = "gitops-test"
    #   value   = "chaijunkin.github.io"
    #   type    = "CNAME"
    #   proxied = true
    # }

    # "home" = {
    #     name = "@"
    #     value = "chaijunkin.github.io"
    #     type = "CNAME"
    #     proxied = true
    # }
    "home-www" = {
      name    = "www"
      value   = "chaijunkin.github.io"
      type    = "CNAME"
      proxied = true
    }
    # "home" = {
    #   name    = "@"
    #   value   = "chaijunkin.github.io"
    #   type    = "CNAME"
    #   proxied = true
    # }
    "vaultwarden" = {
      name    = "vw"
      value   = var.vaultwarden_private_url
      type    = "CNAME"
      proxied = true
      ### STEP 1 turn this off and terraform apply
      ### STEP 2 remove certificate and create again
      ### fly certs remove vw.{SECRET_DOMAIN} --app {SECRET_APP}
      ### fly certs add vw.{SECRET_DOMAIN} --app {SECRET_APP}
      ### STEP 3 turn this on
    }
    "gatus" = {
      name    = "status"
      value   = var.gatus_private_url
      type    = "CNAME"
      proxied = false
    }
  }

  github_A_record = [
    "185.199.108.153",
    "185.199.109.153",
    "185.199.110.153",
    "185.199.111.153"
  ]
  github_AAAA_record = [
    "2606:50c0:8000::153",
    "2606:50c0:8001::153",
    "2606:50c0:8002::153",
    "2606:50c0:8003::153"
  ]
}
