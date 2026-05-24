set quiet
set script-interpreter := ['bash', '-euo', 'pipefail']
set shell := ['bash', '-euo', 'pipefail', '-c']

[private]
default:
    just -l sops

AGE_FILE := justfile_directory() / "../age.key"

[doc('Initialize Age Key for Sops')]
[script]
age-keygen:
    if [ ! -f "{{ AGE_FILE }}" ]; then
        age-keygen --output "{{ AGE_FILE }}"
    fi

[doc('Encrypt a specific file in place')]
encrypt-file file:
    sops --encrypt --in-place "{{ file }}"

[doc('Decrypt and re-encrypt all sops secrets')]
[script]
re-encrypt:
    find "{{ justfile_directory() }}/../" -type d -name .archive -prune -o -type f -name '*.sops.yaml' ! -name ".sops.yaml" -print | while read -r file; do
        sops --decrypt --in-place "$file"
        sops --encrypt --in-place "$file"
    done
