Auto approve PR

```
gh pr list  --author "app/cjk-bot" | awk '{print $1}' | xargs -I {} gh pr review {} --approve
```

Auto merge EVERY PR (riskier, no checking CI)
```
gh pr list --author "app/cjk-bot" | awk '{print $1}' | xargs -I {} gh pr merge {} --merge --admin
```

Auto merge EVERY PR
```
gh pr list --author "app/cjk-bot" --limit 100 --search "status:success" --json number --jq '.[].number' | xargs -I {} gh pr merge {} --merge --delete-branch
```

```
for id in $(gh pr list --author "app/cjk-bot" --app ${{ secrets.BOT_USERNAME }} --jq '.[].number' --json number); do
    gh pr merge $id --squash
done
```