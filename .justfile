#!/usr/bin/env -S just --justfile

set lazy
set quiet
set shell := ['bash', '-euo', 'pipefail', '-c']

# Ansible Recipes
[group: 'Ansible']
mod ansible "infrastructure/ansible"

# Bootstrap Recipes
[group: 'Bootstrap']
mod bootstrap "bootstrap"

# Fly.io Recipes
[group: 'Fly.io']
mod fly "infrastructure/flyio"

# GitHub Recipes
[group: 'GitHub']
mod github ".just/github.just"

# Kube Recipes
[group: 'Kube']
mod kube "kubernetes"

# Sops Recipes
[group: 'Sops']
mod sops ".just/sops.just"

# Talos Recipes
[group: 'Talos']
mod talos "kubernetes/talos"

# Workstation Recipes
[group: 'Workstation']
mod workstation ".just/workstation.just"

[private]
default:
    just -l

[private]
log lvl msg *args:
    echo -e "$(date -u +"%Y-%m-%dT%H:%M:%SZ") \033[1m[{{ lvl }}]\033[0m {{ msg }} {{ args }}"

[private]
template file *args:
    minijinja-cli "{{ file }}" {{ args }}

# ----------------- REPOSITORY MANAGEMENT -----------------

[group: 'Repository']
[doc('Initialize configuration files')]
init:
    mkdir -p .private
    if [ ! -f config.yaml ]; then \
        cp config.sample.yaml config.yaml; \
        echo "=== Configuration file copied ==="; \
        echo "Proceed with updating the configuration files..."; \
        echo "config.yaml"; \
    fi

[group: 'Repository']
[doc('Configure repository from bootstrap vars')]
[script]
configure: init
    just workstation direnv
    just workstation venv
    just sops age-keygen
    just repo-template
    # just sops encrypt
    just validate

[private]
repo-template:
    .venv/bin/makejinja

[private]
validate:
    just kube kubeconform

[group: 'Repository']
[doc('Clean files and directories no longer needed after bootstrap')]
[script]
clean:
    rm -rf .github/tests
    rm -rf .github/workflows/e2e.yaml
    mv bootstrap .private/bootstrap-$(date +%H%M%S)
    mv makejinja.toml .private/makejinja-$(date +%H%M%S).toml
    sed -i '' 's/(..\.j2)\?//g' .github/renovate.json5

[group: 'Repository']
[confirm('Reset templated configuration files [y|N] ?')]
[doc('Reset templated configuration files')]
reset:
    just ansible clean || true
    just talos reset || true
    # sops reset is commented out in Taskfile

[group: 'Repository']
[confirm('Reset repository back to HEAD [y|N] ?')]
[doc('Reset repo back to HEAD')]
[script]
force-reset: reset
    git reset --hard HEAD
    git clean -f -d
    git pull origin main

[group: 'ci']
gitleaks-run:
    gitleaks git --report-path gitleaks-report.json .

# default gitleaks will run on git, will run on `dir` on demand