# Starter prompts for Claude Code

One prompt per person. Paste yours as the first message in a new Claude Code chat (VS Code extension) opened on your clone of this repository. Claude also reads `.claude/CLAUDE.md` automatically.

Before the first session: `gh auth login`, `pnpm install`, `tools/scripts/py-setup.sh`. During the v1.0 sprint your one open issue is your `[Sxx]` sprint issue; work its batches in order (tier 1 first) and read [../sprint-v1.0.md](../sprint-v1.0.md).

| Person | Prompt | Sprint issue (29 Oct to 6 Nov 2026) |
|---|---|---|
| Faizan (@faizanrooman) | [faizan.md](faizan.md) | `[S01] Sprint v1.0: Faizan` |
| Himanshu (@himanshu-rooman) | [himanshu.md](himanshu.md) | `[S02] Sprint v1.0: Himanshu` |
| Praveen (@praveen-rooman) | [praveen.md](praveen.md) | `[S03] Sprint v1.0: Praveen` |
| Shivani (@shivanisinghrooman-09) | [shivani.md](shivani.md) | `[S04] Sprint v1.0: Shivani` |
| Akshata (@akshatatrathodrooman) | [akshata.md](akshata.md) | `[S05] Sprint v1.0: Akshata` |
| Ashritha (@Ashritharooman) | [ashritha.md](ashritha.md) | `[S06] Sprint v1.0: Ashritha` |
| Gokula Lakshmi (@gokulalakshmirooman-source) | [gokula-lakshmi.md](gokula-lakshmi.md) | `[S07] Sprint v1.0: Gokula Lakshmi` |
| Tejaswini (@tejaswini-rooman) | [tejaswini.md](tejaswini.md) | `[S08] Sprint v1.0: Tejaswini` |
| Madhumita (@madhumitha-rooman) | [madhumita.md](madhumita.md) | `[S09] Sprint v1.0: Madhumita` |
| Srujan (@srujanrooman) | [srujan.md](srujan.md) | `[S10] Sprint v1.0: Srujan` |

## Resuming in a later session

````markdown
Continue my Education OS work. Follow `.claude/CLAUDE.md` and `docs/team/RULES.md`.
1. Run `git status`, `git branch --show-current` and `gh issue list --assignee @me --state open`.
2. If my branch's issue is closed, switch to `main`, pull, and start a new branch for the new issue.
3. Otherwise `git fetch origin && git rebase origin/main`, then tell me what is done, what is left for the issue, and the next step.
Stay inside the paths I own, run `tools/scripts/precheck.sh` before any push, and do not write code until I confirm the next step.
````

Why these prompts prevent merge conflicts: each person changes only their own modules, touches another module only for widget files with the owner reviewing, never edits shared configuration, works on one issue per branch, and rebases daily with a fixed rule for the lockfile.
