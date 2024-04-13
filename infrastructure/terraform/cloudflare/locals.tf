
locals {
  cloudflare_zone_name  = var.cloudflare_zone_name
  cloudflare_account_id = var.cloudflare_account_id
  cloudflare_api_token  = var.cloudflare_api_token

  mail_txt_value = var.mail_txt_value
  mail_mx1_value = var.mail_mx1_value
  mail_mx2_value = var.mail_mx2_value
  mail_spf_value = var.mail_spf_value
  dkim_value     = var.dkim_value
  dmarc_value    = var.dmarc_value

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

    "home" = {
        name = "@"
        value = "chaijunkin.github.io"
        type = "CNAME"
        proxied = true
    }
    "home-www" = {
      name    = "www"
      value   = "cloudjur.com"
      type    = "CNAME"
      proxied = true
    }
    "vaultwarden" = {
      name  = "vw"
      value = "blue-cherry-8641.fly.dev"
      type  = "CNAME"
    }
    "external-uptimekuma" = {
      name  = "ext-uptime"
      value = "uptime-kuma-rdm12exn709.fly.dev"
      type  = "CNAME"
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