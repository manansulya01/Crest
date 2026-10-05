# CLI

```
crest init [--root P]
crest status
crest config
crest capabilities list|show <id>|revoke <id> [--reason R]
crest receipts list|show <id>
crest audit [--limit N]
crest policy check --tool T --operation O [--arg k=v]...
crest verify --action A --recovery KIND [--scope S] [--target T] [--trials N] [--seed N]
crest exec <tool> <operation> [--arg k=v]...
```

Exit codes: 0 ok; 3 denied/security failure; 4 not found; argparse errors: 2.

Examples:

```bash
crest exec filesystem create_file --arg path=tmp/a.txt --arg content=hello
crest exec shell command --arg command="git status"
crest exec git create_branch --arg name=feat/x
```
