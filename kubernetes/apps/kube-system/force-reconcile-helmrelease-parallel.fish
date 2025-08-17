for line in (kubectl get helmrelease -A -o custom-columns="NAMESPACE:.metadata.namespace,NAME:.metadata.name" --no-headers)
    set ns (echo $line | awk '{print $1}')
    set name (echo $line | awk '{print $2}')
    flux reconcile hr -n $ns $name --force &
end
wait
