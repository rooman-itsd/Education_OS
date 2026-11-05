#!/usr/bin/env bash
# Every commit on a PR must be a conventional commit scoped by module:
#   feat(admissions): add merit list      fix(tenancy): approval twice returned 500
#   chore(repo): ..., docs(team): ..., test(lms): ..., refactor(x): ..., ci(repo): ...
# Usage: tools/scripts/check-commits.sh <base-sha> <head-sha>
set -euo pipefail
BASE="${1:?base}"; HEAD="${2:?head}"
PATTERN='^(feat|fix|docs|test|refactor|chore|ci|perf|build)\([a-z0-9-]+\): .{8,}$'
bad=0
while IFS= read -r line; do
  subject="${line#* }"
  if ! [[ "$subject" =~ $PATTERN ]]; then echo "bad commit message: $subject"; bad=1; fi
done < <(git log --no-merges --format='%H %s' "$BASE..$HEAD")  # merge commits vanish in the squash merge
[ $bad -eq 0 ] && echo "commit messages ok"
exit $bad
