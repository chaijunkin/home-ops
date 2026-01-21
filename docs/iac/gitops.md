Auto approve PR

```
gh pr list  --author "app/cjk-bot" | awk '{print $1}' | xargs -I {} gh pr review {} --approve
```

Auto merge EVERY PR
```
gh pr list --author "app/cjk-bot" | awk '{print $1}' | xargs -I {} gh pr merge {} --merge --admin
```

```
for id in $(gh pr list --author "app/cjk-bot" --app ${{ secrets.BOT_USERNAME }} --jq '.[].number' --json number); do
    gh pr merge $id --squash
done
```