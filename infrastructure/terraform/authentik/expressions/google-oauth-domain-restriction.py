oauth_userinfo = request.context.get("oauth_userinfo")

# If this is not an OAuth login, show the prompt (return True)
if not oauth_userinfo:
    return True

# It is an OAuth login, get the email
email = oauth_userinfo.get("email", "")

# Verify the domain
if "@" in email:
    current_domain = email.split("@")[1]
    
    # We allow the domain passed via terraform template
    if current_domain == "${domain}":
        # Auto-set the prompt data
        request.context["prompt_data"] = {
            "username": email,
            "email": email,
            "name": oauth_userinfo.get("name", email.split("@")[0]),
        }
        # Skip the prompt stage
        return False

# If the domain doesn't match, block the flow
return ak_message(f"Access denied. Email domain {current_domain} is not authorized.")
