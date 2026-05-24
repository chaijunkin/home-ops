set quiet
set script-interpreter := ['bash', '-euo', 'pipefail']
set shell := ['bash', '-euo', 'pipefail', '-c']

[private]
default:
    just -l github

[doc('Set GitHub Secrets for Fly.io integration')]
[script]
secrets-set:
    fly_token=$(fly tokens org -j --org jun-kin-c-jk | jq -r '.token')
    gh secret set FLY_API_TOKEN -b "$fly_token"
    
    json=$(for d in "{{ justfile_directory() }}/../infrastructure/flyio"/*; do
      [ -f "$d/.config.env" ] || continue
      app=$(basename "$d")
      flyv=$(grep -E '^FLY_APP=' "$d/.config.env" | head -n1 | sed -E 's/^FLY_APP=(.*)/\1/' | tr -d '\r"')
      [ -n "$flyv" ] || continue
      jq -nc --arg app "$app" --arg fly "$flyv" '{app_name:$app,fly_app_name:$fly}'
    done | jq -s '.')
    
    gh secret set FLY_APP -b "$json"

[doc('Trigger Fly Deploy GitHub workflow')]
deploy:
    gh workflow run fly-deploy.yaml
