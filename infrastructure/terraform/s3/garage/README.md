## remove all state
```
terraform state list | cut -f 1 -d '[' | xargs -L 1  terraform state rm
```


## import existing postgresql bucket
```
terraform import 'module.garage["postgresql"].garage_bucket.bucket' postgresql
```
