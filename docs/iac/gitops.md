Auto approve PR

```
gh pr list | awk '{print $1}' | xargs -I {} gh pr review {} --approve
```

Auto merge EVERY PR
```
gh pr list | awk '{print $1}' | xargs -I {} gh pr merge {} --merge --admin
```

```
for id in $(gh pr list --app ${{ secrets.BOT_USERNAME }} --jq '.[].number' --json number); do
    gh pr merge $id --squash
done
```