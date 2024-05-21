#!/usr/bin/env fish

# Define the JSON data directly within the script
set -l json_data '
{
  "jobs": [
    {"namespace": "downloads", "job_name": "repair-prowlarr-091041"},
    {"namespace": "downloads", "job_name": "repair-qbittorrent-091041"},
    {"namespace": "downloads", "job_name": "repair-radarr-091041"},
    {"namespace": "downloads", "job_name": "repair-readarr-091041"},
    {"namespace": "downloads", "job_name": "repair-sonarr-091041"},
    {"namespace": "downloads", "job_name": "unlock-bazarr-091102"},
    {"namespace": "downloads", "job_name": "unlock-prowlarr-091103"},
    {"namespace": "downloads", "job_name": "unlock-qbittorrent-091102"},
    {"namespace": "downloads", "job_name": "unlock-radarr-091103"},
    {"namespace": "downloads", "job_name": "unlock-readarr-091103"},
    {"namespace": "downloads", "job_name": "unlock-sonarr-091103"},
    {"namespace": "home-automation", "job_name": "repair-home-assistant-091041"},
    {"namespace": "home-automation", "job_name": "unlock-home-assistant-091103"},
    {"namespace": "media", "job_name": "repair-filebrowser-091041"},
    {"namespace": "media", "job_name": "repair-overseerr-091041"},
    {"namespace": "media", "job_name": "repair-paperless-091041"},
    {"namespace": "media", "job_name": "repair-plex-091041"},
    {"namespace": "media", "job_name": "repair-tautulli-091041"},
    {"namespace": "media", "job_name": "unlock-filebrowser-091103"},
    {"namespace": "media", "job_name": "unlock-overseerr-091103"},
    {"namespace": "media", "job_name": "unlock-paperless-091103"},
    {"namespace": "media", "job_name": "unlock-plex-091103"},
    {"namespace": "media", "job_name": "unlock-tautulli-091103"},
    {"namespace": "downloads", "job_name": "repair-sonarr-090903"},
    {"namespace": "downloads", "job_name": "repair-readarr-090803"},
    {"namespace": "downloads", "job_name": "repair-bazarr-090703"},
    {"namespace": "downloads", "job_name": "repair-qbittorrent-090603"}
  ]
}
'

# Loop through each job and namespace pair using jq to parse the JSON data
for job in (echo $json_data | jq -c '.jobs[]')
    set namespace (echo $job | jq -r '.namespace')
    set job_name (echo $job | jq -r '.job_name')

    # Delete the job in the specified namespace
    echo "Deleting job $job_name in namespace $namespace"
    kubectl delete job $job_name -n $namespace
end
