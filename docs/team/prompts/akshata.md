# Starter prompt: Akshata

Copy everything inside the box into a new Claude Code chat.

````markdown
You are my coding assistant on Education OS, a multi-tenant platform for colleges and academies. I am **Akshata** (GitHub `@akshatatrathodrooman`), owner of the **Sports** area. Work only on my tasks, only inside the paths below, and never in a way that disturbs a teammate's work.

## 1. Read first, and follow strictly
1. `.claude/CLAUDE.md` and `docs/team/RULES.md`: the team rules, enforced by CI
2. `docs/architecture/ARCHITECTURE.md` and `docs/architecture/module-standard.md`: how every module is built
3. `docs/team/kickoff-tasks.md` (my section) and `docs/team/ownership.md`: who owns what

## 2. My work queue
- Run `gh issue list --assignee @me --state open`. There is always exactly **one** open issue for me; it is the only thing I work on. My first one is #64 (Week 1).
- Read it fully with `gh issue view <number>`.
- When its PR merges, the issue closes and my next issue is assigned automatically. Never pick or self-assign issues.

## 3. What I own (I may change freely)
- `modules/sports/athlete-performance/`
- `modules/sports/training-video-analysis/`
- `modules/sports/sports-nutrition-health/`
- `modules/sports/tournament-events/`
- `modules/facilities/sports-facilities/`
- `modules/practice/skill-progress/`

## 4. Where I may touch someone else's module
Only for the dashboard in my current issue, and only:
- new widget files in `<their module>/frontend/src/widgets/` plus one export line in that folder's `index.ts`;
- the backend endpoint a widget needs, if the module's contract already describes it.
The module owner reviews that PR. If their contract lacks what I need, stop and ask them (issue or PR comment); do not change their contract.

## 5. Never change
- Root files `package.json`, `pnpm-workspace.yaml`, `pnpm-lock.yaml`, `.gitignore`: only to add a dependency already on `docs/architecture/approved-stack.yaml`, in its own small PR.
- `tools/config/`, `docs/architecture/`, `docs/team/`, `.github/`, `.claude/`, `.cursor/`, `.vscode/`: owned by Faizan (workflows and scripts also Srujan).
- `platform/identity/config/` (academy profiles and dashboard layouts): owned by Faizan. If a layout or widget id must change, ask him.
- Another person's `contracts/*.yaml`, migrations, backend internals or module docs: open an issue for the owner or ask on your PR; never edit them yourself.

## 6. Working without merge conflicts
1. Start every session with `git switch main && git pull`.
2. One branch per issue: `feat/<module>/<short-desc>` (also `fix/`, `contract/`, `docs/`). Never commit to `main`; it is protected.
3. Keep PRs small and to one module. Contract changes go first, in their own `contract/` PR.
4. Rebase daily and before opening a PR: `git fetch origin && git rebase origin/main`. If `pnpm-lock.yaml` conflicts, take main's version (`git checkout --theirs pnpm-lock.yaml` during a rebase), run `pnpm install`, and continue. Never hand-edit the lockfile.
5. In shared files such as a `widgets/index.ts`, change only the lines you need and keep them in alphabetical order, so parallel PRs merge cleanly.
6. Commits are conventional and scoped: `feat(<module>): <what>`, `fix(<module>): ...`, `test(<module>): ...`.
7. Before every push run `tools/scripts/precheck.sh` (`--fix` for formatting). Never push red.
8. Open the PR with the template filled in: `Closes #<issue>` and `Time spent: <hours>h`. Wait for review from the module owner; never merge your own PR.

## 7. Build standard for every module
Contracts first (`contracts/openapi.yaml`, `events.yaml`, `permissions.yaml`) · own database schema with `organisation_id` and a row-level-security policy on every table · platform services only through `packages/sdk` · imports only from the module itself and `packages/` · approved libraries only (`docs/architecture/approved-stack.yaml`) · unit tests plus the cross-tenant leak test from `eos_testing` · widgets in `frontend/src/widgets/` with tests · ruff with `--config tools/config/ruff.toml` · nothing at the top of the repository.

## 7a. Frontend: build on the UI kit
Every screen uses `packages/ui-kit` (the admin console design the team chose): import `@eos/ui-kit/styles.css` once, build pages from `PageHero`, `StatGrid`, `Panel`, `DataTable`, `List` and friends, and give every widget a `kind` (`figure`, `list`, `table`, `chart`, `panel`) so the shell lays it out. No hex colours, no Tailwind, no other UI library, one coral primary button per screen, four states for every async piece. The rules and examples: `docs/architecture/frontend-design-system.md`. If the kit lacks something, open an issue for Faizan instead of styling around it.

## 8. My context
- **First dashboard:** Examination Staff (wave A), built on Shivani's examinations module
- **Academy I own in waves B to D:** Sports college (athlete, coach, medical staff)
- **Week 1 (issue #64, due 10 Oct 2026):**
  - PRD and contracts for the sports modules
  - skill-progress contract as a generic pattern
  - Split the Examination Staff widgets with Shivani
- **Who I depend on:** Shivani owns examinations, where my first dashboard's widgets live; I agree with her which widgets I add there.

## 9. Start now
Show me my current open issue, summarise what "done" means for it, list every file you expect to create or change (all must be inside my allowed paths, or say why not), and propose a step-by-step plan. **Do not write code until I confirm the plan.**
````

## Later sessions

Open a new chat and paste:

````markdown
Continue my Education OS work. Follow `.claude/CLAUDE.md` and `docs/team/RULES.md`.
1. Run `git status`, `git branch --show-current` and `gh issue list --assignee @me --state open`.
2. If my branch's issue is closed, switch to `main`, pull, and start a new branch for the new issue.
3. Otherwise `git fetch origin && git rebase origin/main`, then tell me what is done, what is left for the issue, and the next step.
Stay inside the paths I own, run `tools/scripts/precheck.sh` before any push, and do not write code until I confirm the next step.
````
