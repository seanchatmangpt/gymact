# gymact migration plan v26.11.16

Standing: UNVERIFIED

## Identity
- Path: /Users/sac/gymact
- Remote: https://github.com/seanchatmangpt/gymact.git
- Branch: main@03393bb0 (upstream origin/main)
- Last commit: 2026-10-13; commits: 2748; size: 150 MB
- Languages/build: Python/uv (pyproject.toml, uv.lock), justfile, Rust (rust/), ggen,
  Docker, k8s packs, zensical.toml
- Nested repos: none

## Observed state
- Dirty: 0; untracked: 2 (docs/jira/v26.11.4/, docs/sjira/v26.10.8/doc-hdit.receipts.jsonl)
- Ahead/behind origin/main: 0/0; stash: 0
- Unpushed local branches: 52 (agent/*, brce-*, ci/*, closure/* ...; several do track an
  origin branch, the rest are local-only feature branches)
- Build dirs: none present; .git 33M; artifacts 24K
- Local-only: .env (secrets — never print), .env.example, data/
- Submodules: none

## What it is
gymact: a decision-court / agent-gym platform with receipts, OCEL feeds, capability pins,
ontology-driven generation (ggen) and A2A agent cards. Large, actively developed.

## Classification
ACTIVE (census agrees)

## Migration risk
- 52 local branches, unknown subset unpushed
- .env with real credentials; data/ may hold local-only datasets
- Two untracked catalogue files
Rating: MEDIUM

## Recommended action
COMMIT-PUSH
1. `cd /Users/sac/gymact && git add docs/jira/v26.11.4 docs/sjira && git commit -m "docs: catalogue"`
2. `git push origin main`
3. `git for-each-ref --format='%(refname:short) %(upstream)' refs/heads | awk 'NF==1'` to
   list branches without upstream, then `git push -u origin <branch>` for each worth keeping
4. DECISION: prune dead agent/* and closure/* branches instead of pushing all 52
5. DECISION: .env — copy to password manager, never to the archive volume in plain text
6. DECISION: data/ — rsync to archive if not regenerable
7. `rm -rf .venv rust/target` before any copy
8. On new machine: `git clone https://github.com/seanchatmangpt/gymact.git`

## First commands on the new machine
`uv sync && just check` (or `uv run pytest`)

## See Also
- ../v26.11.4/
- /Users/sac/docs/jira/v26.11.16/README.md
