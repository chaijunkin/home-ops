set quiet
set script-interpreter := ['bash', '-euo', 'pipefail']
set shell := ['bash', '-euo', 'pipefail', '-c']

[private]
default:
    just -l ansible

ANSIBLE_DIR := justfile_directory()
VIRTUAL_ENV := justfile_directory() / "../../.venv"
ANSIBLE_INVENTORY_FILE := ANSIBLE_DIR / "inventory/hosts.yaml"
ANSIBLE_REQUIREMENTS_FILE := ANSIBLE_DIR / "requirements.yaml"
ANSIBLE_PIP_REQUIREMENTS_FILE := ANSIBLE_DIR / "requirements.txt"
ANSIBLE_LINT_FILE := ANSIBLE_DIR / ".ansible-lint"

[doc('Set up Ansible dependencies')]
[script]
deps:
    "{{ VIRTUAL_ENV }}/bin/python3" -m pip install --upgrade --requirement "{{ ANSIBLE_PIP_REQUIREMENTS_FILE }}"
    "{{ VIRTUAL_ENV }}/bin/ansible-galaxy" install --role-file "{{ ANSIBLE_REQUIREMENTS_FILE }}" --force

[confirm('Run Ansible playbook ' + playbook + ' ?')]
[doc('Run an Ansible playbook')]
run playbook *args: deps
    "{{ VIRTUAL_ENV }}/bin/ansible-playbook" --inventory "{{ ANSIBLE_INVENTORY_FILE }}" "{{ ANSIBLE_DIR }}/playbooks/{{ playbook }}.yaml" {{ args }}

[confirm('Shutdown all Kubernetes nodes via Ansible ?')]
[doc('Shutdown all Kubernetes nodes')]
poweroff: deps
    "{{ VIRTUAL_ENV }}/bin/ansible" kubernetes --inventory "{{ ANSIBLE_INVENTORY_FILE }}" -a '/usr/bin/systemctl poweroff' --become

[doc('List all Ansible hosts')]
list: deps
    "{{ VIRTUAL_ENV }}/bin/ansible" kubernetes --inventory "{{ ANSIBLE_INVENTORY_FILE }}" --list-hosts

[doc('Ping all Ansible hosts')]
ping: deps
    "{{ VIRTUAL_ENV }}/bin/ansible" kubernetes --inventory "{{ ANSIBLE_INVENTORY_FILE }}" --one-line -m 'ping'

[doc('Show uptime of all Ansible hosts')]
uptime: deps
    "{{ VIRTUAL_ENV }}/bin/ansible" kubernetes --inventory "{{ ANSIBLE_INVENTORY_FILE }}" --one-line -a 'uptime'

[doc('Lint Ansible files')]
lint: deps
    "{{ VIRTUAL_ENV }}/bin/ansible-lint" --config-file "{{ ANSIBLE_LINT_FILE }}" "{{ ANSIBLE_DIR }}"/**/*.yaml
