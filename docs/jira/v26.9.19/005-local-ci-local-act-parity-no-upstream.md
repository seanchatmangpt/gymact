# gymact: push or delete local-only branch `ci/local-act-parity`

- Standing: OPEN
- Created: 2026-09-19 (v26.9.19 gh survey wave)
- Source: local branch `ci/local-act-parity` has 6 commit(s) not on `origin/main`, no upstream
- Evidence: `git rev-list --count origin/main..ci/local-act-parity` = 6

## Work to complete
- Push (`git push -u origin ci/local-act-parity`) if the work matters; otherwise delete the branch after confirming the commits are obsolete.

## Acceptance
- Branch pushed and visible on GitHub, or deleted locally with commits confirmed recoverable-or-unwanted.

## History
- 2026-09-19 | OPEN | survey found local-only branch | ci/local-act-parity (6 commits) | decision pending
