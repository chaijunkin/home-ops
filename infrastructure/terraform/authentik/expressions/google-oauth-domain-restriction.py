allowed_domains = ["${domain}"]
current_domain =request.context["prompt_data"]["email"].split("@")[1]
if current_domain in allowed_domains:
  email = request.context["prompt_data"]["email"]
  request.context["prompt_data"]["username"] = email
  request.context["prompt_data"]["name"] = email
  return ak_is_sso_flow
else:
  return ak_message("Access denied for this email domain")