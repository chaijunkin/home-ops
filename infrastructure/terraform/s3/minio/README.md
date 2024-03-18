## remove all state
```
terraform state list | cut -f 1 -d '[' | xargs -L 1  terraform state rm 
```