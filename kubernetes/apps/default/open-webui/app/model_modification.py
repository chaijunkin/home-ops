import requests
import json
import re

# --- Configuration ---
#
# !!! IMPORTANT: REPLACE THESE PLACEHOLDERS WITH YOUR ACTUAL VALUES !!!
#
OPEN_WEBUI_BASE_URL = ""  # Replace with your Open WebUI URL
API_KEY = ""       # Replace with your Open WebUI Bearer Token
# ---------------------


HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


def get_models():
    """
    Fetches the current list of models from the Open WebUI API.
    Handles nested JSON structures (e.g., list under 'models' key).
    """
    url = f"{OPEN_WEBUI_BASE_URL}/api/models"
    print(f"Attempting to fetch models from: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)

        # Check for HTTP errors (4xx or 5xx)
        if response.status_code != 200:
            print(f"\n--- API ERROR RESPONSE ({response.status_code}) ---")
            print(f"Failed to fetch models.")
            if response.status_code == 401:
                print("ISSUE: Authentication Failed (401 Unauthorized). Check your API_KEY.")
            elif response.status_code == 404:
                print(f"ISSUE: Endpoint Not Found (404). Check the base URL: {OPEN_WEBUI_BASE_URL}")
            else:
                print(f"Details: {response.text}")
            print(f"----------------------------------")
            return None

        data = response.json()

        # --- NEW LOGIC: Handle nested model list ---
        if isinstance(data, dict):
            # Try to extract the list from a common key
            if 'models' in data and isinstance(data['models'], list):
                print("Found model list nested under 'models' key.")
                return data['models']
            if 'data' in data and isinstance(data['data'], list):
                print("Found model list nested under 'data' key.")
                return data['data']

        # If it's a list at the root (expected by prior versions), return it directly
        if isinstance(data, list):
            print("Found model list as root-level array.")
            return data

        # If we got here, the structure is unexpected
        print(f"\n--- PARSING ERROR ---")
        print(f"API returned a 200 OK, but the JSON structure was unexpected.")
        print(f"Received data type: {type(data)}")
        print(f"---------------------")
        return None

    except requests.exceptions.ConnectionError as e:
        print(f"\n--- FATAL CONNECTION ERROR ---")
        print(f"ISSUE: Could not connect to Open WebUI at {OPEN_WEBUI_BASE_URL}.")
        print(f"Original error details: {e}")
        print(f"------------------------------")
        return None
    except requests.exceptions.Timeout:
        print(f"\n--- FATAL TIMEOUT ERROR ---")
        print(f"ISSUE: Request timed out after 10 seconds. The server is unreachable or very slow.")
        print(f"---------------------------")
        return None
    except requests.exceptions.RequestException as e:
        print(f"An unexpected request error occurred: {e}")
        return None

def update_model_status(model_data, is_active):
    """
    Updates the active status of a specific model using the dedicated
    POST /api/v1/models/model/update endpoint.

    It sends the model ID in the query parameter and the ENTIRE model object
    (with the updated is_active status and mandatory fields) in the request body.
    """

    # 1. Start with the full model data as the payload
    payload = model_data.copy()

    # CRITICAL FIX: Ensure mandatory fields required by the /update endpoint schema exist
    # These fields must be present at the top level of the payload object
    if 'meta' not in payload:
        payload['meta'] = {}
    if 'params' not in payload:
        payload['params'] = {}

    # 2. Apply the update: explicitly set the new active state
    payload['is_active'] = is_active

    # Get ID for URL and logging
    model_id = payload['id']

    # URL structure with ID as query parameter, using the /update endpoint
    url = f"{OPEN_WEBUI_BASE_URL}/api/v1/models/model/update?id={model_id}"

    try:
        # Use POST for the update operation
        response = requests.post(url, headers=HEADERS, data=json.dumps(payload))
        response.raise_for_status()

        return True
    except requests.exceptions.RequestException as e:
        # Include status code and response text for debugging update errors
        status_code = getattr(response, 'status_code', 'N/A')
        response_text = getattr(response, 'text', 'No response text')

        # Critical warning for the 401 error
        if status_code == 401:
            print(f"!!! CRITICAL: Received 401 Unauthorized for {model_id}. !!!")
            print(f"!!! Ensure your API_KEY is correct and has administrator/edit permissions. !!!")

        print(f"Error updating model {model_id}: Status {status_code} - {response_text}")

        return False

def disable_target_models():
    """
    Main function to fetch models, filter them (external, non-'free', and active),
    and explicitly disable their status using the update endpoint.
    """
    models_data = get_models()

    # Check if models_data is None (due to network/auth/parsing error) or empty list
    if models_data is None or not isinstance(models_data, list) or not models_data:
        print("Could not retrieve model list or the list is empty. Exiting.")
        return

    target_models = []

    # 1. Filter models
    for model in models_data:
        model_name = model.get('name', '')
        connection_type = model.get('connection_type')

        # Check if the model is currently active/enabled
        is_active = model.get('is_active', model.get('enabled', True))

        # Filter for 'external', NON-'free', and CURRENTLY ACTIVE models to disable them
        if connection_type == 'external' and is_active:
            if not re.search(r'free', model_name, re.IGNORECASE):
                target_models.append(model)

    if not target_models:
        print("No models found matching the criteria (external, active, and non-'free').")
        return

    print(f"\nSuccessfully retrieved model list. Found {len(target_models)} models to disable:")
    for model in target_models:
        print(f"  - ID: {model['id']}, Name: {model['name']}")

    print("\n--- Disabling Models ---")

    # 2. Disable filtered models.
    success_count = 0
    fail_count = 0
    for model in target_models:
        # Pass the entire model dictionary and False to explicitly disable
        if update_model_status(model, False):
            print(f"[SUCCESS] Disabled: {model['name']}")
            success_count += 1
        else:
            print(f"[FAILED] Could not disable: {model['name']}")
            fail_count += 1

    print("\n--- Summary ---")
    print(f"Total models filtered: {len(target_models)}")
    print(f"Successfully disabled: {success_count}")
    print(f"Failed to disable: {fail_count}")

if __name__ == "__main__":
    disable_target_models()