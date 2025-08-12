#!/usr/bin/env fish
# kubectl get ingress --all-namespaces -o json | jq -r '.items[] | .spec.rules[]?.host' | sort | uniq

set input "hostnames.txt"
set output "output.csv"

# Write CSV header
echo "title,subtitle,arg" > $output

# Read each line (hostname) from the input file
for host in (cat $input)
    set title $host
    set subtitle "Ingress host for $host"
    set arg $host
    echo "$title,$subtitle,$arg" >> $output
end
