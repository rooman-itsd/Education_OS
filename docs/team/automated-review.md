# Automated review and approval on the lead's behalf

Two workflows. `.github/workflows/auto-review.yml` reviews every pull request that asks Faizan for a review or
touches a path he is a code owner of (`.github/CODEOWNERS`: platform core, `packages/`, `docs/architecture/`,
`docs/team/`, `.github/`, `tools/`, `infra/`, `apps/`, `tests/`), on open, on every new commit, when the PR
leaves draft and when a reviewer is requested; a review of an older commit is cancelled by the next one.
`.github/workflows/auto-approve.yml` then posts the verdict as Faizan's review.

What happens:
1. The branch is checked out, `tools/scripts/py-setup.sh` installs every enabled package from it, `pnpm install` runs.
2. Claude Code (Sonnet; Opus when platform core or `apps/backend/src` changes) reads the diff and the rules, runs
   the affected suites, ruff and the repository checks, tries to reproduce anything it suspects, and writes a verdict.
3. The verdict is posted as a comment review by the workflow and uploaded as an artifact. **This job holds no
   credential that can approve or merge**, because it runs the pull request's own code.
4. `auto-approve.yml` runs afterwards from `main`'s copy of itself, downloads the artifact, re-checks that the PR
   head is still the reviewed commit, the author is in `docs/team/members.yaml`, the PR is open and not a draft,
   and then, with Faizan's token: "request changes" with the findings when something would block a reviewer (a
   bug, a security or tenancy gap, a rule violation, red tests), otherwise "approve".
5. The merge watcher merges approved, green PRs within minutes; a new push starts over.

**Deployment-critical paths keep a human approval.** A PR that changes `.github/`, `tools/`, `infra/`, `apps/`,
`packages/` or `platform/` gets the bot's review and a comment with its verdict, but no automatic approval:
those paths decide what runs in CI, on the servers and in the host, and a verdict is derived from the pull
request's own content (its text can steer the model, its tests run before the verdict is written). For module
code the lead accepted that residual risk on 31 October 2026, after the reviewer's objection on #393, because
the alternative was to remain the bottleneck for every module PR. If the verdict is ever wrong, the approval
is a normal review that a code owner can dismiss, and the watcher merges only when CI is green.

Not reviewed or approved automatically: drafts, PRs by authors outside `members.yaml`, Faizan's own PRs.

## Setup (repository admin, once)
Settings → Secrets and variables → Actions:
- `CLAUDE_CODE_OAUTH_TOKEN`: the long-lived token `claude setup-token` prints (uses Faizan's Claude subscription).
  Alternative with separate API billing: `ANTHROPIC_API_KEY`, and change the action input to `anthropic_api_key`.
- `FAIZAN_REVIEW_TOKEN`: a fine-grained personal access token of @faizanrooman, repository
  `rooman-itsd/Education_OS`, permission "Pull requests: Read and write" only. Used by `auto-approve.yml` alone.

## For authors
The review reads like a human's: fix the findings, push, and the next run re-reviews and re-approves. If the
verdict is wrong, say so on the PR; the prompt in `auto-review.yml` is where the rules live.
