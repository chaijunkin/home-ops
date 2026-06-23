local function host_matches(host)
  if not host then
    return false
  end

  host = string.match(host, "([^:]+)") or host
  return host == "wiki.cloudjur.com" or host == "schema.cloudjur.com"
end

local function is_extensionless_html_path(path)
  if not path or path == "" then
    return false
  end

  local path_only = string.match(path, "^([^?]*)")
  if not path_only or path_only == "/" then
    return false
  end

  if string.sub(path_only, -1) == "/" then
    return false
  end

  return string.find(path_only, "%.[^/]+$") == nil
end

function envoy_on_request(request_handle)
  local user_agent = request_handle:headers():get("user-agent") or ""
  local blocked_patterns = {
    "Meta-ExternalAgent",
    "meta-webindexer",
    "GPTBot",
    "CCBot",
    "Google-Extended",
    "Bytespider",
    "Amazonbot",
    "Applebot-Extended"
  }

  for _, pattern in ipairs(blocked_patterns) do
    if string.find(user_agent, pattern, 1, true) then
      request_handle:respond({[":status"] = "200"}, "")
      return
    end
  end

  local host = request_handle:headers():get(":authority") or request_handle:headers():get("host")
  if not host_matches(host) then
    return
  end

  local path = request_handle:headers():get(":path") or ""
  if not is_extensionless_html_path(path) then
    return
  end

  local path_only, query = string.match(path, "^([^?]*)(.*)$")
  request_handle:headers():replace(":path", path_only .. ".html" .. (query or ""))
end
