# Automated review (advisory)

`.github/workflows/auto-review.yml` reviews every pull request that asks Faizan for a review or touches a path
he is a code owner of (`.github/CODEOWNERS`: platform core, `packages/`, `docs/architecture/`, `docs/team/`,
`.github/`, `tools/`, `infra/`, `apps/`, `tests/`). It runs on open, on every new commit, when the PR leaves
draft and when a reviewer is requested; a review of an older commit is cancelled by the next one.

What happens:
1. The branch is checked out, `tools/scripts/py-setup.sh` installs every enabled package from it, `pnpm install` runs.
2. Claude Code (Sonnet; Opus when platform core or `apps/backend/src` changes) reads the diff and the rules, runs
   the affected suites, ruff and the repository checks, tries to reproduce anything it suspects, and writes a verdict.
3. The verdict is posted as a **comment review** by the workflow's own token: "Verdict: changes" with the
   findings (file, what, fix) when something would block a reviewer (a bug, a security or tenancy gap, a rule
   violation, red tests), otherwise "Verdict: approve" with follow-ups in the text.
4. A human code owner reads it and approves (or asks for the changes); the merge watcher merges approved PRs.

Why it does not approve by itself: the job runs code from the pull request (its tests and install scripts) and
the model reads the pull request's text, so any credential in that job, or any verdict it produces, can be
steered by the PR. An approval that counts as a code owner's must come from a person. The review removes the
reading and testing work from the reviewer, not the decision.

It does not push, commit, approve or merge; it skips drafts and Faizan's own PRs (his reviewers are Srujan and Himanshu).

## Setup (repository admin, once)
Settings → Secrets and variables → Actions: `CLAUDE_CODE_OAUTH_TOKEN`, the long-lived token `claude setup-token`
prints (uses Faizan's Claude subscription, so reviews count against the same usage as his sessions). Alternative
with separate API billing: `ANTHROPIC_API_KEY`, and change the action input to `anthropic_api_key`.
No other secret: the review is posted with the workflow's `GITHUB_TOKEN`.

## For authors
Read the verdict like a human's: fix the findings, push, and the next run re-reviews. If the verdict is wrong,
say so on the PR; the prompt in the workflow is where the rules live.
