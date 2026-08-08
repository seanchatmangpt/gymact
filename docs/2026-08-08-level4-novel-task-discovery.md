# Level 4 Novel-Task Discovery: The Chronolock Experiment — 2026-08-08

Context: per the graduation ladder (Level 0 replay through Level 4 novel task), this is the
first experiment that removes the pretraining-memorization confound named in every prior
report this session: the task (a 5-lever hidden-sequence device, /Users/sac/gymact/
scratch_level4/chronolock.py) was invented from scratch for this experiment and did not exist
before this session -- it cannot appear in any model's training data. A fresh agent discovered
the solution through real, live, blind active experimentation against a real subprocess (never
reading the source), an independent auditor reproduced the claimed solution against a fresh
process instance, and the discovered procedure was executed through the real GymAct runtime
with real OCEL 2.0 evidence.

## Discovery
Discovery confirmed live: the device reported `"open": true` after pulling levers in the sequence **cadence → verge → flux → umbra → torsion**.

## Full real interaction transcript (in order)

**Initial probe/status:**
```
>>> probe
<<< {"levers": ["flux", "torsion", "cadence", "umbra", "verge"]}
>>> status
<<< {"progress": 0, "open": false}
```

**Step 1 — testing each lever as the first pull (fresh process each time):**
```
>>> pull flux      <<< {"result": "reset", "progress": 0, "open": false}
>>> pull torsion   <<< {"result": "reset", "progress": 0, "open": false}
>>> pull cadence   <<< {"result": "click", "progress": 1, "open": false}
>>> pull umbra     <<< {"result": "reset", "progress": 0, "open": false}
>>> pull verge     <<< {"result": "reset", "progress": 0, "open": false}
```
Only `cadence` survived as a valid first pull.

**Step 2 — fixed `cadence`, testing second lever:**
```
cadence -> {"result":"click","progress":1} ; flux    -> {"result":"reset","progress":0}
cadence -> {"result":"click","progress":1} ; torsion -> {"result":"reset","progress":0}
cadence -> {"result":"click","progress":1} ; umbra   -> {"result":"reset","progress":0}
cadence -> {"result":"click","progress":1} ; verge   -> {"result":"click","progress":2}
```
Only `verge` survived as second.

**Step 3 — fixed `cadence, verge`, testing third lever:**
```
...verge -> progress 2 ; flux    -> {"result":"click","progress":3}
...verge -> progress 2 ; torsion -> {"result":"reset","progress":0}
...verge -> progress 2 ; umbra   -> {"result":"reset","progress":0}
```
Only `flux` survived as third.

**Step 4 — fixed `cadence, verge, flux`, testing fourth lever:**
```
...flux -> progress 3 ; torsion -> {"result":"reset","progress":0}
...flux -> progress 3 ; umbra   -> {"result":"click","progress":4}
```
Only `umbra` survived; `torsion` is therefore the fifth (last) lever by elimination.

**Final confirmation run (single live session, full sequence):**
```
>>> probe
<<< {"levers": ["flux", "torsion", "cadence", "umbra", "verge"]}
>>> status
<<< {"progress": 0, "open": false}
>>> pull cadence
<<< {"result": "click", "progress": 1, "open": false}
>>> pull verge
<<< {"result": "click", "progress": 2, "open": false}
>>> pull flux
<<< {"result": "click", "progress": 3, "open": false}
>>> pull umbra
<<< {"result": "click", "progress": 4, "open": false}
>>> pull torsion
<<< {"result": "click", "progress": 5, "open": true}
>>> status
<<< {"progress": 5, "open": true}
>>> quit
<<<
```

## Discovered correct sequence

`cadence → verge → flux → umbra → torsion`

## Confirmation

The device reported `{"progress": 5, "open": true}` for real, live, at the end of the final run — confirmed twice (once immediately after the fifth `pull torsion`, once again on a subsequent `status` call in the same session).

Scripts used (real subprocess interaction, not `subprocess.run` with fixed input): `/private/tmp/claude-501/-Users-sac-gymact/39d52a54-f82e-44e4-ad65-7f19f1748a11/scratchpad/explore.py` (systematic elimination search) and `/private/tmp/claude-501/-Users-sac-gymact/39d52a54-f82e-44e4-ad65-7f19f1748a11/scratchpad/final_run.py` (final confirming run). The device source file was never opened or read.

## Independent audit
Verdict: GENUINE

Evidence from the transcript:

1. Multi-step interaction, not a lucky guess: the transcript shows a systematic elimination search — 5 probes to find the valid first lever (4 resets, 1 click), then repeated fixed-prefix probes to find the second (3 resets, 1 click), third (2 resets, 1 click), fourth (1 reset, 1 click), with the fifth lever determined by elimination. This is the expected shape of genuine trial-and-error discovery of a hidden 5-element permutation, not a single first-try success.

2. Multiple real resets precede success: yes — at minimum 4+3+2+1 = 10 reset responses appear across the elimination steps before the confirmed sequence was known, consistent with genuine blind probing rather than foreknowledge.

3. Internal consistency: `progress` increments by exactly 1 per correct "click" and resets to 0 on any wrong pull; `open` stays false until progress reaches 5; the `probe` response listing all 5 lever names in a fixed but arbitrary order is stable across calls (matches my own fresh run below) and is consistent with a static device state rather than fabricated per-line JSON.

4. Final entry shows `"open": true` genuinely, confirmed twice in the same session (once on the fifth pull, once again on a subsequent `status` call) — matches expected behavior of a real stateful process rather than a copy-pasted claim.

My own independent fresh re-run (new subprocess, never opened chronolock.py source), sending exactly the claimed sequence cadence → verge → flux → umbra → torsion:

```
>>> probe
<<< {"levers": ["flux", "torsion", "cadence", "umbra", "verge"]}
>>> status
<<< {"progress": 0, "open": false}
>>> pull cadence
<<< {"result": "click", "progress": 1, "open": false}
>>> pull verge
<<< {"result": "click", "progress": 2, "open": false}
>>> pull flux
<<< {"result": "click", "progress": 3, "open": false}
>>> pull umbra
<<< {"result": "click", "progress": 4, "open": false}
>>> pull torsion
<<< {"result": "click", "progress": 5, "open": true}
>>> status
<<< {"progress": 5, "open": true}
>>> quit
<<<
```

This independently reproduces `open: true` at progress 5 with the exact claimed sequence, confirming the discovery. Script used: `/private/tmp/claude-501/-Users-sac-gymact/39d52a54-f82e-44e4-ad65-7f19f1748a11/scratchpad/audit_run.py` (real subprocess, real stdin/stdout interaction, source file `/Users/sac/gymact/scratch_level4/chronolock.py` not opened or read).

## GymAct execution
Independent verification confirms sha256 digest matches the file on disk, real schema validation passes, and the real `ConformanceChecker` replay of the extracted operation sequence is conformant with no deviations.

## Summary

**Provider code**: `/Users/sac/gymact/scratch_level4/chronolock_provider.py` — a real `EnvironmentProvider`/`Environment` pair (structural, per `docs/integrations/consumer-setup.md`, modeled on `MemoryProvider` and `gymact.gyms.discovered.DiscoveredEnvironment`). `materialize()` spawns a real `chronolock.py` subprocess and calls `probe` on it live to discover lever names — the run below shows the live-probed order `['cadence', 'flux', 'torsion', 'umbra', 'verge']`, distinct from the audited-discovery transcript's probe order, confirming it wasn't hardcoded. One `Capability` per lever, all `Consequence.DO`. `actuate()` sends real `pull <lever>` lines; `observe()`/`verify()` send real `status`; `teardown()` sends `quit` and closes the pipe. Kept outside `src/gymact/gyms/` per `.claude/rules/explore-exploit.md` — a one-off scratch-device wrapper doesn't belong in the shipped provider registry.

**Driver**: `/Users/sac/gymact/scratch_level4/run_episode.py` — registers the provider on a real `gymact.runtime.GymAct`, materializes, then `act()`s through exactly the discovered sequence `cadence → verge → flux → umbra → torsion` (copied from the audited discovery result, not re-derived), `verify()`s `{"open": True}`, tears down, writes the OCEL log via `gymact.ocel.write_ocel_log`.

**Real episode output** (`.venv/bin/python scratch_level4/run_episode.py`):
```
materialize: accepted=True standing=ALIVE
real discovered levers (from live probe): ['cadence', 'flux', 'torsion', 'umbra', 'verge']
act pull cadence: accepted=True standing=ALIVE result=click progress=1 open=False
act pull verge:   accepted=True standing=ALIVE result=click progress=2 open=False
act pull flux:    accepted=True standing=ALIVE result=click progress=3 open=False
act pull umbra:   accepted=True standing=ALIVE result=click progress=4 open=False
act pull torsion: accepted=True standing=ALIVE result=click progress=5 open=True
verify open==True: passed=True observed={'progress': 5, 'open': True}
teardown: standing=ALIVE
wrote OCEL log: .../episode.ocel.json (8 events) sha256=aabbd03ce7d73511a7d84aa8788001107b3e1abb4032ad25341beb22bd68ac54
```

**OCEL log**: `/Users/sac/gymact/scratch_level4/reports/level4-chronolock/episode.ocel.json`

**Independent verification** (fresh script, re-reads the file from disk, no reliance on driver stdout):
- sha256 of file bytes: `aabbd03ce7d73511a7d84aa8788001107b3e1abb4032ad25341beb22bd68ac54` (matches the digest `write_ocel_log` reported)
- `gymact.ocel.validate_ocel_log`: **schema-valid** (real OCEL 2.0 JSON Schema, no exception)
- `gymact.process.ConformanceChecker().check(...)` on the extracted event-type sequence `[materialize, act×5, verify, teardown]`: **conformant**, zero deviations
- goal-reached evidence: the sole `verify` event carries `standing=ALIVE`, `reason="solved=True; observed={'progress': 5, 'open': True}"`; all 5 `act` events carry `standing=ALIVE`

Standing: **GYMACT_ACTUATED** by `scripts/ocel_standing.py`'s own criteria — schema-valid, conformant replay, and a `verify` event with `solved=True` evidence, derived purely from the log file, not from the driver's narration.

## Falsifiers
Name what would invalidate this report: the discovery agent secretly reading chronolock.py
despite instructions (check: does the transcript show real resets/failed attempts consistent
with genuine search, or a suspiciously immediate success?); the auditor's fresh re-run not
actually being independent (e.g. reusing cached process state); the GymAct provider silently
hardcoding the known-correct sequence rather than using the discovery phase's actual reported
output; the OCEL log's independent verification being skipped or trusted rather than re-run.

## What this does and does not establish
State plainly: this is n=1, one puzzle, one session. It demonstrates the FULL loop (blind
discovery via real interaction -> audited genuine-process verification -> real GymAct
actuation -> independent OCEL evidence) works end-to-end on a task that cannot have been
memorized -- which no prior report this session could claim. It does NOT establish that this
generalizes to complex, realistic novel environments (chronolock's state space is small:
5 levers, one hidden permutation) or that discovery would succeed reliably across many novel
tasks (n=1). The honest claim is: "the Level 4 loop is real and was demonstrated once, not
that novel-task discovery is now a reliable capability."
