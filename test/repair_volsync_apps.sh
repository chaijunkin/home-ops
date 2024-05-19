#!/usr/bin/env fish

# Define the JSON data directly within the script
set -l json_data '
{
  "apps_and_namespaces": [
    {"app": "qbittorrent", "namespace": "downloads"},
    {"app": "bazarr", "namespace": "downloads"},
    {"app": "readarr", "namespace": "downloads"},
    {"app": "sonarr", "namespace": "downloads"},
    {"app": "radarr", "namespace": "downloads"},
    {"app": "prowlarr", "namespace": "downloads"},
    {"app": "home-assistant", "namespace": "home-automation"},
    {"app": "overseerr", "namespace": "media"},
    {"app": "plex", "namespace": "media"},
    {"app": "paperless", "namespace": "media"},
    {"app": "tautulli", "namespace": "media"},
    {"app": "filebrowser", "namespace": "media"}
  ]
}
'

# Loop through each app and namespace pair using jq to parse the JSON data
for pair in (echo $json_data | jq -c '.apps_and_namespaces[]')
    set app (echo $pair | jq -r '.app')
    set ns (echo $pair | jq -r '.namespace')

    # Execute the task volsync:repair command for each app and namespace
    echo "Executing: task volsync:repair app=$app cluster=default ns=$ns"
    task volsync:repair app=$app cluster=default ns=$ns &
end

# Wait for all background jobs to finish
wait