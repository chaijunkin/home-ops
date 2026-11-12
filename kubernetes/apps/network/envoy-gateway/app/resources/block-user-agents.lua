local function host_matches(host)
  if not host then
    return false
  end

  host = string.match(host, "([^:]+)") or host
  return host == "wiki.cloudjur.com" or host == "schema.cloudjur.com" or host == "read.cloudjur.com"
end

-- Garage only serves the emitted `<slug>.html`, so URL slugs must be suffixed
-- here. Slugs may legitimately contain dots ("fly.io-…", Obsidian ".base"
-- pages), so decide by whether the LAST dot-segment is a real static-asset
-- extension — not by the mere presence of a dot.
local static_asset_extensions = {
  css = true, js = true, mjs = true, map = true, json = true, xml = true,
  txt = true, ico = true, png = true, jpg = true, jpeg = true, gif = true,
  svg = true, webp = true, avif = true, webmanifest = true, woff = true,
  woff2 = true, ttf = true, otf = true, eot = true, mp4 = true, pdf = true,
  rss = true, atom = true
}

local function needs_html_suffix(path)
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

  local ext = string.match(path_only, "%.([^/.]+)$")
  if ext and static_asset_extensions[string.lower(ext)] then
    return false
  end

  return true
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
  if not needs_html_suffix(path) then
    return
  end

  local path_only, query = string.match(path, "^([^?]*)(.*)$")
  request_handle:headers():replace(":path", path_only .. ".html" .. (query or ""))
end
