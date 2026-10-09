# CAMPAIGN-RECEIPT — gymact v26.10.8

| Field | Value |
|---|---|
| Branch | `main` |
| HEAD | `ea87c1913ae722930a60f0d00da17d951b6ddd2b` (concurrent fleet lanes were landing during receipt write; HEAD re-read at write time) |
| Base tag | `v26.10.8` (`da1558f8f46b74ca39c96540c9e52ae3ceb97c66`) |
| In-sync with origin | in sync at receipt time |

## Campaign commits since `v26.10.8`

| SHA | Subject |
|---|---|
| `ea87c191` | docs: SJ-008 triage baseline explanation page (fleet campaign) |
| `e76dac50` | Merge origin/main (d21b465b: same Diataxis restructure landed via an earlier consolidated commit); keep split commit history |
| `b4de3cc9` | docs: rewrite index as Diataxis authority map; update nav and cross-links |
| `344dd3c5` | docs: move flat docs into Diataxis quadrants |
| `d21b465b` | docs: restructure docs/ into Diataxis quadrants (moves) |
| `e7012dfc` | docs: cross-reference SA2A envelope surface (fleet campaign) |
| `270ec8cf` | docs: sync narrative version framing to 26.10.8 + changelog Fixed entry |
| `06835b9d` | Merge branch 'v26926/gymact-land-aloop-execution-kernel' — v26.10.8 fleet campaign (fix surfaces version drift, SA2A replan envelope, survival CLI) |

## Witnessed gates

| Gate | Result |
|---|---|
| SJ-008 triage | Triage completed; every finding classified environment-bound (all-env-bound), no product defects |
| Post-merge test run | 27/27 tests passing after merge `e76dac50` |

## Standing

ALIVE — SJ-008 closed all-env-bound; post-merge suite green.

## Open residues

| Residue | Detail |
|---|---|
| History wart | `d21b465b` (consolidated Diataxis restructure) duplicates the split-commit restructure `344dd3c5`+`b4de3cc9`; both retained on `main` via merge `e76dac50`. History only; no tree drift. |
