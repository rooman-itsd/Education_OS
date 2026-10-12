# Team rules

These rules are enforced by GitHub and CI, not by memory. A pull request that breaks one cannot
merge. The lead (Faizan) owns this file; changing a rule is a PR to it.

## 1. The stack is fixed

Only what is listed in [docs/architecture/approved-stack.yaml](../architecture/approved-stack.yaml)
may appear in any `package.json` or `pyproject.toml`. CI runs `tools/scripts/check-stack.py` and
fails otherwise. Want a library? Open a PR that adds it to the list with a one-line reason; the
Architecture lead approves or declines. Forbidden outright: axios, lodash, moment, redux, MUI,
Bootstrap, jQuery, Django, Flask, requests.

| Layer | Use |
|---|---|
| Frontend | React 18, TypeScript, Vite, React Router, TanStack Query, react-hook-form + zod, generated OpenAPI clients, `@eos/ui-kit` components |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, arq for jobs |
| Data | PostgreSQL 16 with row-level security, Redis, OpenSearch, MinIO |
| Tests | Vitest and Testing Library; pytest; Playwright for end to end |
| Quality | ruff, mypy, ESLint, Prettier |

## 2. Nothing reaches main without a pull request

`main` is protected: no direct pushes, no force pushes, linear history. The lead's admin account
may bypass review in an emergency; nobody else can. Every PR needs

- every required check green: `api / test`, `web / build`, `governance / rules`;
- one approving review from a code owner of every file touched (`.github/CODEOWNERS`);
- every review conversation resolved;
- the PR template filled in: module, task link, time spent.

Red CI is never "fixed later". A PR that is red is not reviewed. Run `tools/scripts/precheck.sh`
before every push; it is the same set of checks CI runs. The admin bypass is for outages, not for
red checks; a bypass is noted in the PR and reviewed at the next standup.

## 3. One module per pull request

Repo-wide housekeeping that has to touch many modules at once (moving shared config, renames)
carries the `repo-wide` label, which only the lead applies; it skips the one-module check and still
needs every other check and review.

A PR touches one module (`modules/<domain>/<module>`, `platform/<service>` or
`integrations/<adapter>`) unless it is a contract change plus its consumers. CI counts the modules
touched. Branch names: `feat/<module>/<short-desc>`, `fix/<module>/<short-desc>`,
`contract/<module>/<short-desc>`.

## 4. Commit messages are conventional and scoped

`feat(admissions): add merit list generation`, `fix(tenancy): approve twice returned 500`,
`test(lms): course materials widget`, `docs(team): week 2 tasks`. CI rejects anything else.

## 5. Module boundaries are law

A module imports only from itself and `packages/`. Platform services may import other platform
services only when declared in `module.yaml`. CI runs `tools/scripts/check-boundaries.py`. Every
table carries `organisation_id` with an RLS policy; every module runs the cross-tenant leak test.
Full list: [module-standard.md](../architecture/module-standard.md).

## 6. Work is tracked in GitHub Issues and the project board

Board: https://github.com/users/faizanrooman/projects/1 (every issue, with Wave and Status).
Issues: https://github.com/faizanrooman/Education_OS/issues. Status report:
https://github.com/faizanrooman/Education_OS/blob/team-status/STATUS.md.

- Every dashboard and every week's task is an issue, with labels `wave:A..D`, `area:<area>`,
  `type:dashboard|task|bug`. **One open issue per person.** When yours closes, the next one in your
  queue is assigned to you automatically within a minute (`.github/workflows/auto-assign.yml`):
  your own issues in the global order shown by the `[NNN]` number in every issue title (milestone
  M1 to M5; within each: week 1, foundation, modules, dashboards by wave, production), then the pool
  in the same order. The whole road
  to production is already on the board as issues with milestones M1 to M5; there is no waiting for
  the next assignment and no picking. Handles live in `docs/team/members.yaml`.
- An issue closes through its PR (`Closes #N`). When your PR merges, the issue it closes is closed and
  your next issue is assigned to you on the spot. A PR that is one part of an issue says `Part of #N`
  and leaves it open; the last PR for the issue says `Closes #N`. A PR that references no issue gets
  a reminder. Done means merged and visible on the live site. Closing an issue by hand without a PR
  is reverted.
- Link the issue in the PR (`Closes #123`) so it closes on merge. Unlinked PRs are sent back.
- Put `Time spent: <hours>h` in the PR body. It feeds the team status report.

## 7. Reviews within one working day

A code owner reviews within one working day or says when they will. The author addresses every
comment or explains why not. Nobody merges their own PR without a review.

## 8. Definition of done, per task

Contracts reviewed · migrations with `organisation_id` and RLS · backend with tests that pass
alone · widget in `frontend/src/widgets/` with tests · Playwright journey for a dashboard ·
`config/env.example` complete · README and CHANGELOG updated · audit events for every state
change · permission keys registered · issue closed by the PR · status updated in the plan doc.

## 9. Visibility

`docs/team/STATUS.md` on the `team-status` branch is regenerated every 6 hours from GitHub: per
person, issues open and closed, PRs merged, average time to merge, average task cycle time, time
spent, CI pass rate, last activity. The lead reads it; everyone can read it. The weekly review
uses it and the plan doc, nothing else.

## 10. Secrets and data

No secrets in git, ever (`.env*` files are ignored; `*.example` files are templates). No real
student data in tests or seeds. Server access is by SSH key, never shared passwords.

## 11. Nothing outside the folders

The top of the repository holds only the folders and the four files listed in
[tools/config/repo-layout.yaml](../../tools/config/repo-layout.yaml): `.gitignore`, `package.json`,
`pnpm-workspace.yaml`, `pnpm-lock.yaml`, which git and pnpm require there. Every other file goes in
its folder: documentation in `docs/`, GitHub files in `.github/`, tool configuration in `tools/config/`,
scripts in `tools/scripts/`, deployment in `infra/`, code inside its module. A new top-level folder
needs a PR to the layout file, approved by the lead.

This applies to people and to every AI assistant equally. CI fails any PR that breaks it
(`tools/scripts/check-root.py`, also run by `precheck.sh`). Claude Code, GitHub Copilot and Cursor read
the same rules automatically from `.claude/CLAUDE.md`, `.github/copilot-instructions.md` and
`.cursor/rules/repository-rules.mdc`, and a Claude Code hook refuses to write files at the top level.
Using any other assistant? Give it `docs/team/RULES.md` first. Each person's starter prompt for
Claude Code, with their owned paths and conflict rules, is in [prompts/](prompts/).
