# Automated review on the lead's behalf

`.github/workflows/auto-review.yml` reviews every pull request that asks Faizan for a review or touches a path
he is a code owner of (`.github/CODEOWNERS`: platform core, `packages/`, `docs/architecture/`, `docs/team/`,
`.github/`, `tools/`, `infra/`, `apps/`, `tests/`). It runs on open, on every new commit, when the PR leaves
draft and when a reviewer is requested; a review of an older commit is cancelled by the next one.

What happens:
1. The branch is checked out, `tools/scripts/py-setup.sh` installs every enabled package from it, `pnpm install` runs.
2. Claude Code (Sonnet; Opus when platform core or `apps/backend/src` changes) reads the diff and the rules, runs
   the affected suites, ruff and the repository checks, tries to reproduce anything it suspects, and writes a verdict.
3. The verdict is posted as a GitHub review **from Faizan's token**, so it counts as a code owner's approval:
   "request changes" with the findings (file, what, fix) when something would block a reviewer (a bug, a
   security or tenancy gap, a rule violation, red tests), otherwise "approve" with follow-ups in the text.
4. The merge watcher merges approved, green PRs within minutes; a new push starts over.

What it does not do: push, commit, or merge by itself; review Faizan's own PRs (his reviewers are Srujan and
Himanshu); review drafts.

## Setup (repository admin, once)
Settings → Secrets and variables → Actions:
- `ANTHROPIC_API_KEY`: an Anthropic API key (API billing). Alternative that uses the subscription instead:
  `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`, and change the action input in the workflow to
  `claude_code_oauth_token`.
- `FAIZAN_REVIEW_TOKEN`: a fine-grained personal access token of @faizanrooman, repository
  `rooman-itsd/Education_OS`, permission "Pull requests: Read and write" only, one-year expiry. Rotate it when it expires.

Without the secrets the workflow runs and posts a comment saying the review could not complete; nothing is approved.

## For authors
The review reads like a human's: fix the findings, push, and the next run re-reviews. If the verdict is wrong,
say so on the PR; Faizan reads every disagreement, and the prompt in the workflow is where the rules live.
