set quiet
set script-interpreter := ['bash', '-euo', 'pipefail']
set shell := ['bash', '-euo', 'pipefail', '-c']

[private]
default:
    just -l workstation

WORKSTATION_RESOURCES_DIR := justfile_directory() / "../.taskfiles/workstation/resources"
PIP_REQUIREMENTS_FILE := justfile_directory() / "../requirements.txt"
VIRTUAL_ENV := justfile_directory() / "../.venv"

[doc('Run direnv hooks')]
direnv:
    direnv allow "{{ justfile_directory() }}/.."

[doc('Set up Python virtual environment')]
[script]
venv:
    python3 -m venv "{{ VIRTUAL_ENV }}"
    "{{ VIRTUAL_ENV }}/bin/python3" -m pip install --upgrade pip setuptools wheel
    "{{ VIRTUAL_ENV }}/bin/python3" -m pip install --upgrade --requirement "{{ PIP_REQUIREMENTS_FILE }}"

[doc('Install Arch workstation dependencies')]
[script]
arch:
    helper=$(command -v yay || command -v paru)
    "$helper" -Syu --needed --noconfirm --noprogressbar $(cat "{{ justfile_directory() }}/../.taskfiles/workstation/Archfile" | xargs)

[doc('Set up Homebrew tools')]
brew:
    brew bundle --file "{{ WORKSTATION_RESOURCES_DIR }}/Brewfile"

[doc('Set up Krew tools')]
krew: brew
    kubectl krew install cert-manager cnpg browse-pvc node-shell rook-ceph view-secret
