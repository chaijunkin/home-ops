import requests
import json
import re

# --- Configuration ---
#
# !!! IMPORTANT: REPLACE THESE PLACEHOLDERS WITH YOUR ACTUAL VALUES !!!
#
# Replace with your Open WebUI URL
OPEN_WEBUI_BASE_URL = "https://chat.cloudjur.com"
# Replace with your Open WebUI Bearer Token
API_KEY = ""
# -----------------------------------

# The base URL you know is for OpenRouter
OPENROUTER_URL = "https://openrouter.ai/api/v1"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


def get_models():
    resp = requests.get(f"{OPEN_WEBUI_BASE_URL}/api/models", headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    if isinstance(data, list):
        return data
    return []

def is_free_model(m):
    if isinstance(m, dict):
        name = m.get("name", "").lower()
        mid = m.get("id", "").lower()
        provider = m.get("provider", "").lower()
        return "free" in name or "free" in mid or "free" in provider
    elif isinstance(m, str):
        return "free" in m.lower()
    return False

def get_openai_config():
    resp = requests.get(f"{OPEN_WEBUI_BASE_URL}/openai/config", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()

def update_model_ids_only(config, free_model_ids):
    base_urls = config.get("OPENAI_API_BASE_URLS", [])
    keys = config.get("OPENAI_API_KEYS", [])
    configs = config.get("OPENAI_API_CONFIGS", {})

    # Find index of OPENROUTER_URL
    target_indices = [str(idx) for idx, url in enumerate(base_urls) if url == OPENROUTER_URL]
    if not target_indices:
        print("Error: OPENROUTER_URL not found in OPENAI_API_BASE_URLS:", base_urls)
        return None

    new_configs = {}
    for idx_str in target_indices:
        existing = configs.get(idx_str, {})
        new_config = {
            **existing,
            "enable": True,
            "connection_type": "external",
            "model_ids": free_model_ids
        }
        new_configs[idx_str] = new_config

    payload = {
        # include required fields so API does not reject
        "ENABLE_OPENAI_API": True,
        "OPENAI_API_BASE_URLS": base_urls,
        "OPENAI_API_KEYS": keys,
        "OPENAI_API_CONFIGS": new_configs
    }

    resp = requests.post(f"{OPEN_WEBUI_BASE_URL}/openai/config/update",
                         headers=HEADERS,
                         json=payload)
    if resp.status_code != 200:
        print(f"[FAIL] update config: {resp.status_code} → {resp.text}")
        return None

    print("[OK] Updated config with new model_ids")
    return resp.json()

def main():
    # Step 1: find free model IDs
    models = get_models()
    free_ids = [m["id"] for m in models if is_free_model(m) and isinstance(m, dict)]
    print("Free model IDs found:", free_ids)
    if not free_ids:
        print("No free models detected — exiting.")
        return

    # Step 2: fetch existing config
    config = get_openai_config()
    print("Existing OpenAI config:", json.dumps(config, indent=2))

    # Step 3: update only model_ids for the targeted connection
    new_conf = update_model_ids_only(config, free_ids)
    if new_conf:
        print("Updated config:", json.dumps(new_conf, indent=2))

if __name__ == "__main__":
    main()

