set quiet
set script-interpreter := ['bash', '-euo', 'pipefail']
set shell := ['bash', '-euo', 'pipefail', '-c']

[private]
default:
    just -l fly

# Helper to load FLY_APP from app's .config.env
[private]
[script]
get-app-name app:
    @grep -E '^FLY_APP=' "{{ justfile_directory() }}/{{ app }}/.config.env" | head -n1 | sed -E 's/^FLY_APP=(.*)/\1/' | tr -d '\r"'

[doc('Create a new Fly app')]
[script]
create app:
    cd "{{ justfile_directory() }}/{{ app }}"
    fly_app=$(fly apps create --generate-name 2>&1 | tee /dev/tty)
    echo "$fly_app" | awk -F 'New app created: ' '{print "\n# Fly app name\nFLY_APP="$2}' >> .config.env

[confirm('Destroy Fly app ' + app + ' ?')]
[doc('Destroy a Fly app')]
[script]
destroy app:
    fly_app=$(just fly get-app-name "{{ app }}")
    fly apps destroy "$fly_app"

[doc('Deploy a Fly app')]
[script]
deploy app: (secrets-set app)
    fly_app=$(just fly get-app-name "{{ app }}")
    cd "{{ justfile_directory() }}/{{ app }}"
    fly deploy -a "$fly_app"

[doc('SSH into a Fly app')]
[script]
ssh app:
    fly_app=$(just fly get-app-name "{{ app }}")
    fly ssh console -a "$fly_app"

[doc('Set secrets for a Fly app')]
[script]
secrets-set app:
    fly_app=$(just fly get-app-name "{{ app }}")
    cd "{{ justfile_directory() }}/{{ app }}"
    cat .config.env | fly secrets import -a "$fly_app"

[doc('Create a volume for a Fly app')]
[script]
volume-create app:
    fly_app=$(just fly get-app-name "{{ app }}")
    fly volumes create "{{ app }}_data" --size 1 -a "$fly_app"

[doc('Show logs for a Fly app')]
[script]
logs app:
    fly_app=$(just fly get-app-name "{{ app }}")
    fly logs -a "$fly_app"

[doc('Open the Fly app monitoring page')]
[script]
web app:
    fly_app=$(just fly get-app-name "{{ app }}")
    open "https://fly.io/apps/$fly_app/monitoring"
