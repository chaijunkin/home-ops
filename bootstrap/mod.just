set no-exit-message
set quiet
set script-interpreter := ['bash', '-euo', 'pipefail']
set shell := ['bash', '-euo', 'pipefail', '-c']

[private]
default:
    just -l bootstrap

[confirm('Bootstrap cluster? [y|N]')]
[doc('Bootstrap a Kubernetes cluster end-to-end')]
cluster: ready base apps

[private]
[script]
base: ready
    just log info "Running stage..." "stage" "$(basename "$0")"
    if ! just template "{{ source_directory() }}/resources.yaml.j2" | kubectl apply --server-side --force-conflicts -f -; then
        just log error "Failed to apply base manifests" "stage" "$(basename "$0")"
    fi
    if ! helmfile -f "{{ source_directory() }}/helmfile/crds.yaml" template -q | yq ea -e 'select(.kind == "CustomResourceDefinition")' | kubectl apply --server-side --force-conflicts -f -; then
        just log error "Failed to apply base crds" "stage" "$(basename "$0")"
    fi

[private]
[script]
apps:
    just log info "Running stage..." "stage" "$(basename "$0")"
    if ! helmfile -f "{{ source_directory() }}/helmfile/apps.yaml" sync --hide-notes --args "--take-ownership"; then
        just log error "Failed to sync helmfile" "stage" "$(basename "$0")"
    fi

# Wait until nodes register as Ready=False. They only become Ready=True once the CNI is healthy.
[private]
[script]
ready:
    just log info "Running stage..." "stage" "$(basename "$0")"
    if ! kubectl wait nodes --for=condition=Ready=True --all --timeout=10s &>/dev/null; then
        until kubectl wait nodes --for=condition=Ready=False --all --timeout=10s &>/dev/null; do
            just log info "Nodes not available, waiting for nodes to be available. Retrying in 5 seconds..." "stage" "$(basename "$0")"
            sleep 5
        done
    fi
