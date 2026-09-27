# Fixture provenance (lane-7, ALOOP-ZCODE-DOGFOOD-001)

Copied byte-for-byte from the episode root `~/.zcode/workspace/default/aloop-dogfood-001/`
on 2026-09-25 by lane-7. These are REAL episode artifacts of concurrent sibling
lanes, not synthetic corpora. All execution in this court is
simulated-in-process; the only "real" surfaces here are these records.

| file | origin | class |
|---|---|---|
| `lane1_record.json` | `lane-1/record.json` (engineering-standards + chatman-ecosystem work) | real-dogfood-replay |
| `lane7_prior_manifest.json` | `lane-7/lane-7.manifest.json` — THIS lane's prior incarnation, which died before first execution | real-dogfood-replay |
| `lane7_prior_typeerror_witness.txt` | preserved command/exit/diagnostic of the prior incarnation's first (crashing) run | real-dogfood-replay |
| `lane7_prior_smoke_script.py` | the smoke script that produced the witness | real-dogfood-replay |
| `lane8_validator_antivacuity.py` | `lane-8/validator_antivacuity.py` (receipt-normalizer seam, L8-owned) | real-dogfood-replay |
| `lane10_run.ndjson` | `lane-10/run.ndjson` (wasm4pm replay-oracle work) | real-dogfood-replay |
| `lane10_verdict.json` | `lane-10/verdict.json` — claims `real_lane_manifests.files_scanned: 0`; attacked by `test_dogfood.py` | real-dogfood-replay |

Cross-clock honesty: lane timestamps are unsynchronized (some lanes used
placeholder `00:00:00Z` values), so no test asserts cross-lane event ORDERING;
each test asserts exactly what its fixture bytes show.
