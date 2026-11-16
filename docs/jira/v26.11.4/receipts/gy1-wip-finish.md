# GY-1 WIP-finish — doc-hdit.receipts.jsonl inspection

Standing: PASS

## Inventory

- Subject: `/Users/sac/gymact/docs/sjira/v26.10.8/doc-hdit.receipts.jsonl` (443 bytes, 1 line,
  mtime 2026-10-09 16:58). Untracked (only `??` entry in `git status`; prior session crash
  left it uncommitted).
- Producing pipeline: rust-doc-hdit-pack (`doc-hdit certify`), pack at
  `/Users/sac/ggen-marketplace/packs/rust-doc-hdit-pack` — README.md:40 specifies
  `<docs>/doc-hdit.receipts.jsonl` as the default chain path. Pack's own
  `doc-hdit.receipts.jsonl` exists with the same schema.
- Docs surface the receipt certifies: `docs/reference/generated/` (Generated-README.md names
  `doc-hdit scaffold` + pack templates; `reference.md` present). `docs/index.md:26` links it.

## Commands + exits

| Command | Exit | Result |
|---|---|---|
| `wc -l docs/sjira/v26.10.8/doc-hdit.receipts.jsonl` | 0 | `1` line |
| python3 per-line `json.loads` loop | 0 | ok=1 bad=0 — every line parses |
| Schema/gate re-derivation (python) | 0 | verdict ACCEPTED; ts 2026-10-09T16:58:34; S_coverage 0.9790 >= 0.9 PASS; Phi_halluc 0.0 <= 0.001 PASS; Q_density 1.0 >= 0.65 PASS; parent "" (chain head/genesis) |
| `git cat-file -e <subject>` | 1 | SUBJECT_SHA_MISSING — expected: `subject`/`extractor`/`hash` are BLAKE3 content hashes (certify v1), not git object IDs |
| `grep -rn "doc-hdit" (repo, excl .git/deps)` | 0 | referenced only in docs/index.md + Generated-README.md (pipeline/output refs, not the receipts file) |
| `grep -rn "receipts.jsonl" rust-doc-hdit-pack` | 0 | pack README.md:40 documents the path convention |

## Findings

1. Receipt file is complete and valid JSON-lines: 1 line, parses, schema matches the pack's
   certify v1 chain format (fields: extractor, gates, hash, parent, subject, thresholds,
   timestamp, verdict). All three gates pass against their embedded thresholds; verdict
   ACCEPTED is lawful.
2. Pipeline exists and owns the path convention (pack README.md:40); certified docs surface
   (`docs/reference/generated/reference.md`) exists.
3. **Orphan disclosure**: no repo file references `doc-hdit.receipts.jsonl` itself — it is
   unreferenced and untracked. Not partial: single-line chain head with `parent: ""` is the
   lawful genesis record for one certify pass. It is consumer-orphaned (nothing reads it
   yet), not truncated. Coordinator decides landing.
