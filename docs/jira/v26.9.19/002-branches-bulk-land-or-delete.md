# gymact: triage 13 PR-less unmerged remote branches

- Standing: OPEN
- Created: 2026-09-19 (v26.9.19 gh survey wave)
- Source: origin branches not merged into `main` with no open PR
- Evidence: `git branch -r --no-merged origin/main`: agent/terminal-bench-gym agent/vendor-benchmark-coverage-v26-8-7-clean brce-full-chain-test ci/local-act-parity fix/registry-pack-outcome-predicates integrate5/dmedi-solver-corr integrate6/solver-corr pr10-verify preserve/main-wip-20260917 task/codebase-env-generalize-20260903 verify/browsergym-container worktree-agent-a4a0a742148dddf68 worktree-agent-ac79210f914751137

## Work to complete
- Triage each branch: land (open a PR) or delete (`git push origin --delete <branch>`). Work in batches; record decisions in History.

## Acceptance
- `git branch -r --no-merged origin/main` is empty after `git fetch --prune`.

## History
- 2026-09-19 | OPEN | survey found 13 PR-less branches | full list above | triage pending
