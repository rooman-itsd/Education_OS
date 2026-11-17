#!/usr/bin/env bash
# Every commit on a PR must be a conventional commit scoped by module:
#   feat(admissions): add merit list      fix(tenancy): approval twice returned 500
#   chore(repo): ..., docs(team): ..., test(lms): ..., refactor(x): ..., ci(repo): ...
# Usage: tools/scripts/check-commits.sh <base-sha> <head-sha>
set -euo pipefail
BASE="${1:?base}"; HEAD="${2:?head}"
PATTERN='^(feat|fix|docs|test|refactor|chore|ci|perf|build)\([a-z0-9-]+\): .{8,}$'
bad=0
# Read into a variable first: `done < <(git log ...)` ignores git's exit status, so an unknown base printed no commits
# and the script said "commit messages ok" having checked nothing. Under `set -e` a failing git log stops it here.
log="$(git log --no-merges --format='%H %s' "$BASE..$HEAD")"  # merge commits vanish in the squash merge
while IFS= read -r line; do
  [ -n "$line" ] || continue
  subject="${line#* }"
  if ! [[ "$subject" =~ $PATTERN ]]; then echo "bad commit message: $subject"; bad=1; fi
done <<< "$log"
[ $bad -eq 0 ] && echo "commit messages ok"
exit $bad
